"""Section-aware chunking: split on resume headings, then by word window with overlap."""
import re
from dataclasses import dataclass

_SECTION_PATTERNS = {
    "summary": r"summary|profile|objective|about",
    "experience": r"experience|employment|work history|projects",
    "skills": r"skills|technologies|technical skills|competencies",
    "education": r"education|academic|certifications?",
}
_HEADING_RE = re.compile(
    r"^\s*(" + "|".join(f"(?P<{k}>{v})" for k, v in _SECTION_PATTERNS.items()) + r")\s*:?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Chunk:
    chunk_idx: int
    section: str
    text: str


def split_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = [("summary", [])]
    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            name = next(k for k in _SECTION_PATTERNS if match.group(k))
            sections.append((name, []))
        else:
            sections[-1][1].append(line)
    return [(name, "\n".join(lines).strip()) for name, lines in sections if "".join(lines).strip()]


def chunk_text(text: str, max_words: int, overlap_words: int) -> list[Chunk]:
    if overlap_words >= max_words:
        raise ValueError("overlap must be smaller than chunk size")
    step = max_words - overlap_words
    chunks: list[Chunk] = []
    for section, body in split_sections(text):
        words = body.split()
        for start in range(0, len(words), step):
            window = words[start : start + max_words]
            chunks.append(Chunk(len(chunks), section, " ".join(window)))
            if start + max_words >= len(words):
                break
    return chunks
