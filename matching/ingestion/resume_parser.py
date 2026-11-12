"""Heuristic resume parser: name, role, years of experience, skills, summary. No external calls."""
import re
from dataclasses import dataclass
from datetime import date

from matching.ingestion.chunker import split_sections
from matching.skills import display_name, extract_skills, normalize_skill

_RANGE_RE = re.compile(r"\b((?:19|20)\d{2})\s*(?:-|–|—|to)\s*((?:19|20)\d{2}|present|current|now)\b", re.IGNORECASE)
_STATED_RE = re.compile(r"\b(\d{1,2})\+?\s*years?\b", re.IGNORECASE)
_NAME_ROLE_SPLIT = re.compile(r"\s+[-–—|]\s+")
_SKILL_SPLIT = re.compile(r"[,;|•\n]")


@dataclass(frozen=True)
class ParsedResume:
    name: str
    role: str
    years_experience: int
    skills: list[str]
    summary: str


def _years(text: str, today: date) -> int:
    stated = _STATED_RE.search(text)
    if stated:
        return min(int(stated.group(1)), 50)
    spans = []
    for start, end in _RANGE_RE.findall(text):
        end_year = today.year if end.lower() in ("present", "current", "now") else int(end)
        if end_year >= int(start):
            spans.append((int(start), end_year))
    total, current_end = 0, None
    for start, end in sorted(spans):  # union of overlapping ranges
        if current_end is None or start > current_end:
            total += end - start
            current_end = end
        elif end > current_end:
            total += end - current_end
            current_end = end
    return min(total, 50)


def _summary(sections: list[tuple[str, str]], first_line: str) -> str:
    bodies = [body for name, body in sections if name == "summary"]
    if not bodies:
        return ""
    body = bodies[-1]
    if len(bodies) == 1 and body.startswith(first_line):
        body = body[len(first_line):].strip()  # no summary heading: drop the name line
    body = " ".join(body.split())
    if len(body) <= 240:
        return body
    cut = body[:240]
    end = max(cut.rfind(". "), cut.rfind("."))
    return cut[: end + 1] if end > 80 else cut.rstrip() + "..."


def parse_resume(text: str, today: date | None = None) -> ParsedResume:
    today = today or date.today()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    first_line = lines[0] if lines else ""
    parts = _NAME_ROLE_SPLIT.split(first_line, maxsplit=1)
    name = parts[0][:120]
    role = parts[1][:120] if len(parts) > 1 else ""

    sections = split_sections(text)
    if not role:
        experience = next((body for n, body in sections if n == "experience"), "")
        first_entry = experience.splitlines()[0] if experience else ""
        role = first_entry.split(",")[0].strip()[:120]

    skills = list(extract_skills(text))
    seen = {normalize_skill(s) for s in skills}
    skills_body = next((body for n, body in sections if n == "skills"), "")
    for item in _SKILL_SPLIT.split(skills_body):
        item = item.strip()
        if 1 < len(item) <= 40 and normalize_skill(item) not in seen:
            seen.add(normalize_skill(item))
            skills.append(display_name(item))

    return ParsedResume(
        name=name,
        role=role,
        years_experience=_years(text, today),
        skills=skills,
        summary=_summary(sections, first_line),
    )
