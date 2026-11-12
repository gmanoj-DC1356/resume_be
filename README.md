# Talent Copilot - Backend (Django 6.1 + DRF 3.18, Python 3.13)

## Quick start
```bash
python3.13 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/init_dev_env.py   # creates your own local .env (secret key + debug); never commit it
python manage.py migrate
python manage.py seed_sample_data  # optional synthetic candidates for local sample search
python manage.py runserver
python manage.py test
```
Health check: `GET /api/v1/health/`

## Who owns which app (Phase 1)
| App | URL prefix | Owner | Module |
|---|---|---|---|
| `accounts` | `/api/v1/auth/` | Srikanth |
| `screening` | `/api/v1/screening/` | Veeran |
| `matching` | `/api/v1/matching/` | Vinay |
| `vectorsearch` | `/api/v1/vectorsearch/` | Abhyuday |
| `resumes` | `/api/v1/resumes/` | Manoj |
| `interview` | `/api/v1/interview/` | Phase 2 |
| `common` | `/api/v1/health/` | Shared (Error handler, shared utilities) |

Stay inside your own app. If you need something from another app, agree the interface (function or endpoint) with its owner in the PR.

## Conventions (every PR)
- Apps live at the project root next to `config/`.
- Pattern: model -> serializer -> view -> permission -> url -> test. Copy `ping` in your app to start.
- Every endpoint is authenticated by default. Opt out only with an explicit `AllowAny` and a comment saying why.
- Validate all input in serializers (allowlist type/shape/range). No raw SQL string building; use the ORM.
- No secrets, real resumes or candidate data in code, tests or fixtures. Use synthetic data.
- No new dependency without approval (see below).
- Branches: `feature/<app>-<short-name>`; PR needs one reviewer from the owning team and one learner reviewer.

## Dependencies
Approved/in manifest: Django, djangorestframework. **Pending approval (not installed):**
`djangorestframework-simplejwt` (Srikanth, JWT), a PostgreSQL driver `psycopg` (database; dev uses SQLite for now),
`celery` + `redis`, `pymongo`, `boto3`, `pymilvus`. Raise these via the approval process before use.

## Data model (RDM)
Relational tables for users, search history and the resume catalogue. Vectors and resume chunks live in Milvus,
not here; the two stores join on `Resume.candidate_ref` = Milvus `resume_id`.

```
USERS 1 ──< SEARCH_SESSIONS 1 ──< SEARCH_RESULTS >── 1 RESUMES
```

| Table (Django model) | App | Key columns |
|---|---|---|
| `USERS` = Django `auth_user` + `accounts.UserProfile` | `accounts` | `id` PK; `aad_oid` UUID unique; `email`; `name`; `created_at` = `date_joined`; `last_login_at` = `last_login` |
| `SEARCH_SESSIONS` = `matching.SearchSession` | `matching` | `id` PK; `user` FK -> user (CASCADE); `job_title`; `skills_json` JSON list; `jd_text`; `status` (PENDING/RUNNING/COMPLETED/FAILED); `result_count`; `created_at` |
| `SEARCH_RESULTS` = `matching.SearchResult` | `matching` | `id` PK; `session` FK -> SearchSession (CASCADE, `related_name=results`); `candidate_ref` FK -> Resume (PROTECT); `score` float 0..1; `rank_position` >= 1; `created_at` |
| `RESUMES` = `resumes.Resume` | `resumes` | `candidate_ref` PK (char, = Milvus `resume_id`); `resume_uri`; `summary_uri`; `created_at`; parsed at ingest: `display_name`, `role`, `years_experience`, `skills_json`, `summary` |

**Relations**
- User 1:N SearchSession (`user.search_sessions`); SearchSession 1:N SearchResult (`session.results`).
- Resume 1:N SearchResult (`resume.search_results`): a resume can appear in many sessions, once per session.

**Constraints and indexes**
- `SearchResult`: unique (`session`, `candidate_ref`), unique (`session`, `rank_position`), check `0 <= score <= 1`, check `rank_position >= 1`.
- `SearchSession`: index (`user`, `-created_at`) for "my recent searches".
- `UserProfile.aad_oid` unique; one profile per user (`OneToOne`).

**Design decisions**
- `USERS` is split across Django's built-in user (keeps the admin and sessions working, no `AUTH_USER_MODEL` swap on an existing DB) and `UserProfile` (Azure AD fields). Swapping to a custom user model is possible, but it needs a fresh database.
- Every query on sessions/results/resumes must be scoped to the caller (`session.user == request.user`); never fetch by id alone.
- `resume_uri` / `summary_uri` are storage locations. Serve files through an authorised endpoint, never return raw URIs.
- Resume content and candidate data are personal data: only synthetic data in tests/fixtures.
- Ownership: `accounts` and `resumes` models were added by the matching team for the RDM; agree the final shape with those app owners in the PR.

## Search API (screening app)
`POST /api/v1/screening/search/` (authenticated outside DEBUG; local unauthenticated requests are allowed in DEBUG and
recorded under an inactive `local_dev` user). The endpoint (view, serializer, tests) lives in `screening`; it calls the
matching engine `matching.search_service.run_search`, which also owns `SearchSession`/`SearchResult`. Ingest resumes first: `python manage.py ingest_resumes --input-dir data/resumes`.

Search history: `GET /api/v1/matching/sessions/` returns the caller's search history as a list of `{id, title, type,
createdAt}` entries. It supports `type=match|questions`, `query`, ISO-8601 `from`/`to`, and `page` filters. The UI's
unauthenticated DEBUG requests use the same inactive `local_dev` user as local searches. `/api/sessions` is also
available as a compatibility route for the current UI.

Request (camelCase, validated in `screening/serializers.py`):
```json
{ "jobTitle": "Data Engineer", "skills": ["Python", "SQL", "Spark"], "jobDescription": "...", "topN": 10 }
```
`jobTitle` required (<=200 chars); `skills` (<=50 items, <=60 chars each) and `jobDescription` (<=10000 chars): at least one is required;
`topN` 1-50 (default 10). If `skills` is empty, skills are extracted from the title and description.

Response: array ordered best first, each item `resumeId` (`r_<candidate_ref>`), `candidateRef` (`CAND-<8 chars>`), `name`, `role`,
`yearsExperience`, `score` (0-100), `matchedSkills`, `missingSkills` (in the caller's spelling; aliases such as `pyspark` -> `Spark` match), `summary`.
Errors use the shared shape; `503` when the embedding model or Milvus is unavailable.

Scoring (starting values in `matching/conf.py`, tune in Phase 6): chunk similarity from Milvus (cosine) is grouped per resume
(0.7 x best + 0.3 x mean of top 3), rescaled above `SEMANTIC_FLOOR`; final = 0.6 x skill coverage + 0.4 x semantic
(semantic only when there are no skills to compare). Each search is stored as a `SearchSession` + `SearchResult` rows for the caller.

## Known gaps (tracked)
- Auth is session-only until the JWT module lands; Simple JWT approval and security-team confirmation on app-managed passwords are open.
- Login rate limiting, refresh token in http-only cookie: part of the accounts module.
- Database is SQLite locally; PostgreSQL settings come with the driver approval.
