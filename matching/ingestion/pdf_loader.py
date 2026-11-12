"""Safe PDF discovery and text extraction."""
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from pypdf import PdfReader

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadedPdf:
    resume_id: str  # first 16 hex chars of the content hash
    filename: str
    text: str


def iter_pdf_paths(root: Path, max_bytes: int) -> Iterator[Path]:
    """Yield .pdf files directly under root; skip symlinks, oversize and out-of-root paths."""
    root = root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Input folder not found: {root}")
    for path in sorted(root.iterdir()):
        if path.suffix.lower() != ".pdf" or path.is_symlink() or not path.is_file():
            continue
        if not path.resolve().is_relative_to(root):
            logger.warning("Skipping path outside input root: %s", path.name)
            continue
        if path.stat().st_size > max_bytes:
            logger.warning("Skipping %s: exceeds size limit", path.name)
            continue
        yield path


def load_pdf(path: Path, max_pages: int) -> LoadedPdf:
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise ValueError("not a PDF file")
    reader = PdfReader(path)
    if len(reader.pages) > max_pages:
        raise ValueError(f"exceeds page limit ({max_pages})")
    text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    if not text:
        raise ValueError("no extractable text (scanned image? OCR is out of scope)")
    return LoadedPdf(
        resume_id=hashlib.sha256(data).hexdigest()[:16],
        filename=path.name,
        text=text,
    )
