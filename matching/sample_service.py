"""Sample-mode search: returns the seeded sample ranking from the database (via the ORM).

Matched/missing skills are computed against the caller's requested skills; the score and rank are the
stored sample values. Replaced by `search_service.run_search` once real resumes are vectorised.
"""
from django.db import transaction

from matching.models import SearchResult, SearchSession
from matching.presenters import candidate_payload, split_skills
from matching.sample_data import SEED_USERNAME
from matching.search_service import dedupe_skills
from matching.skills import extract_skills, normalize_skill


def run_sample_search(*, user, job_title: str, skills: list[str], jd_text: str, top_n: int) -> list[dict]:
    requested = dedupe_skills(skills) or dedupe_skills(extract_skills(f"{job_title}\n{jd_text}"))

    sample_session = SearchSession.objects.filter(user__username=SEED_USERNAME).order_by("-created_at").first()
    rows = []
    if sample_session is not None:
        rows = list(sample_session.results.select_related("candidate").order_by("rank_position")[:top_n])

    # Record the caller's own search so history reflects it, owned by the caller.
    with transaction.atomic():
        session = SearchSession.objects.create(
            user=user, job_title=job_title, skills_json=requested, jd_text=jd_text,
            status=SearchSession.Status.COMPLETED, result_count=len(rows),
        )
        SearchResult.objects.bulk_create(
            SearchResult(session=session, candidate=r.candidate, score=r.score, rank_position=r.rank_position)
            for r in rows
        )

    payload = []
    for row in rows:
        matched, missing = split_skills(requested, row.candidate.skills_json, normalize_skill)
        payload.append(candidate_payload(row.candidate, row.score, matched, missing))
    return payload
