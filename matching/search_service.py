"""Job search: embed the request, find nearest resume chunks, score and rank candidates."""
import logging
from collections import defaultdict

from django.db import transaction

from matching.conf import get_matching_settings
from matching.embedding.embedder import get_embedder
from matching.models import SearchResult, SearchSession
from matching.presenters import candidate_payload, split_skills
from matching.skills import extract_skills, normalize_skill
from matching.store.milvus_store import get_shared_client, search_chunks
from resumes.models import Resume

logger = logging.getLogger(__name__)


class SearchUnavailable(Exception):
    """Embedding model or vector store could not serve the request."""


def dedupe_skills(skills: list[str]) -> list[str]:
    seen, out = set(), []
    for skill in skills:
        key = normalize_skill(skill)
        if key and key not in seen:
            seen.add(key)
            out.append(skill.strip())
    return out


def _semantic_by_resume(hits: list[dict], floor: float) -> dict[str, float]:
    """Per resume: blend best chunk similarity with the mean of its top 3, rescaled to 0..1."""
    sims: dict[str, list[float]] = defaultdict(list)
    for hit in hits:
        sims[hit["entity"]["resume_id"]].append(float(hit["distance"]))
    scores = {}
    for resume_id, values in sims.items():
        values.sort(reverse=True)
        top = values[:3]
        blended = 0.7 * values[0] + 0.3 * (sum(top) / len(top))
        scores[resume_id] = min(max((blended - floor) / (1 - floor), 0.0), 1.0)
    return scores


def _combine(semantic: float, coverage: float | None, w_skills: float, w_semantic: float) -> float:
    if coverage is None:  # no skills to compare: semantic similarity only
        return semantic
    return (w_skills * coverage + w_semantic * semantic) / (w_skills + w_semantic)


def run_search(*, user, job_title: str, skills: list[str], jd_text: str, top_n: int) -> list[dict]:
    settings = get_matching_settings()
    requested = dedupe_skills(skills) or dedupe_skills(extract_skills(f"{job_title}\n{jd_text}"))

    session = SearchSession.objects.create(
        user=user, job_title=job_title, skills_json=requested, jd_text=jd_text, status=SearchSession.Status.RUNNING
    )
    try:
        query = f"{job_title}. Skills: {', '.join(requested)}. {jd_text}".strip()
        vector = get_embedder().embed_query(query)
        hits = search_chunks(get_shared_client(), settings, vector, settings.search_top_chunks)
    except Exception as exc:
        logger.exception("Search backend failure")
        session.status = SearchSession.Status.FAILED
        session.save(update_fields=["status"])
        raise SearchUnavailable from exc

    semantic = _semantic_by_resume(hits, settings.semantic_floor)
    resumes = Resume.objects.in_bulk(list(semantic))

    scored = []
    for resume_id, sem in semantic.items():
        resume = resumes.get(resume_id)
        if resume is None:  # vector exists but no catalogue row: skip rather than guess
            continue
        matched, missing = split_skills(requested, resume.skills_json, normalize_skill)
        coverage = len(matched) / len(requested) if requested else None
        score = _combine(sem, coverage, settings.weight_skills, settings.weight_semantic)
        scored.append((score, resume, matched, missing))

    scored.sort(key=lambda row: (-row[0], row[1].candidate_ref))
    scored = scored[:top_n]

    with transaction.atomic():
        SearchResult.objects.bulk_create(
            SearchResult(session=session, candidate=resume, score=score, rank_position=rank)
            for rank, (score, resume, _, _) in enumerate(scored, start=1)
        )
        session.status = SearchSession.Status.COMPLETED
        session.result_count = len(scored)
        session.save(update_fields=["status", "result_count"])

    return [candidate_payload(resume, score, matched, missing) for score, resume, matched, missing in scored]
