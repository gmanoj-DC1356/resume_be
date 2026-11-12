"""Shape a candidate for the search API response."""
from resumes.models import Resume

_REF_PREFIX = "CAND-"


def candidate_payload(resume: Resume, score: float, matched: list[str], missing: list[str]) -> dict:
    """`score` is 0..1; the API reports 0..100."""
    ref = resume.candidate_ref
    return {
        "resumeId": resume.external_id or f"r_{ref}",
        "candidateRef": ref if ref.startswith(_REF_PREFIX) else f"{_REF_PREFIX}{ref[:8].upper()}",
        "name": resume.display_name,
        "role": resume.role,
        "yearsExperience": resume.years_experience,
        "score": round(score * 100),
        "matchedSkills": matched,
        "missingSkills": missing,
        "summary": resume.summary,
    }


def split_skills(requested: list[str], resume_skills: list[str], normalize) -> tuple[list[str], list[str]]:
    """Requested skills the resume has / lacks, in the caller's spelling (aliases match via normalize).

    Matched skills follow the resume's own skill order; missing skills follow the request order.
    """
    spelling = {normalize(s): s for s in requested}
    matched, seen = [], set()
    for skill in resume_skills:
        key = normalize(skill)
        if key in spelling and key not in seen:
            seen.add(key)
            matched.append(spelling[key])
    missing = [s for s in requested if normalize(s) not in seen]
    return matched, missing
