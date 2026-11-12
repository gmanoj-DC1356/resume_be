+----------------------+
|        USERS         |
+----------------------+
| id (PK)              |
| aad_oid (UNIQUE)     |
| email                |
| name                 |
| created_at           |
| last_login_at        |
+----------------------+
           |
           | 1 : N
           |
           v

+----------------------+
|   SEARCH_SESSIONS    |
+----------------------+
| id (PK)              |
| user_id (FK)         |
| job_title            |
| skills_json          |
| jd_text              |
| status               |
| result_count         |
| created_at           |
+----------------------+
           |
           | 1 : N
           |
           v

+----------------------+
|   SEARCH_RESULTS     |
+----------------------+
| id (PK)              |
| session_id (FK)      |
| candidate_ref        |
| score                |
| rank_position        |
| created_at           |
+----------------------+

+----------------------+
|       RESUMES        |
+----------------------+
| candidate_ref (PK)   |
| resume_uri           |
| summary_uri          |
| created_at           |
+----------------------+