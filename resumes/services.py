"""Finding a resume by its public id and turning its stored location into a file the viewer may serve."""
import io
import logging
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlparse
from urllib.request import url2pathname

from django.conf import settings

from .models import Resume
from .sample_pdf import PDF_MAGIC, build_sample_pdf

logger = logging.getLogger(__name__)

# The id the UI uses is `external_id`, or `r_<candidate_ref>` when none is set (see matching.presenters).
DERIVED_ID_PREFIX = "r_"
FILE_SCHEME = "file"
SAMPLE_SCHEME = "sample"
LOCAL_HOSTS = ("", "localhost")


class ResumeFileUnavailable(Exception):
    """The resume has no file the viewer may serve. Callers answer with one generic 404."""


def find_resume(public_id: str) -> Resume | None:
    by_external_id = Resume.objects.filter(external_id=public_id).first()
    if by_external_id is not None:
        return by_external_id
    if not public_id.startswith(DERIVED_ID_PREFIX):
        return None
    # The derived id only names resumes that have no external id of their own.
    return Resume.objects.filter(candidate_ref=public_id.removeprefix(DERIVED_ID_PREFIX), external_id="").first()


def public_id_of(resume: Resume) -> str:
    return resume.external_id or f"{DERIVED_ID_PREFIX}{resume.candidate_ref}"


def _resolve_inside_root(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != FILE_SCHEME or parsed.netloc not in LOCAL_HOSTS:
        raise ResumeFileUnavailable("not a local file location")
    root = Path(settings.RESUME_FILES_ROOT).resolve()
    try:
        # resolve() follows symlinks, so a link that points outside the root is caught below.
        path = Path(url2pathname(parsed.path)).resolve(strict=True)
    except OSError as error:
        raise ResumeFileUnavailable("file not found") from error
    if not path.is_relative_to(root) or path.suffix.lower() != ".pdf" or not path.is_file():
        raise ResumeFileUnavailable("file is outside the resume folder or is not a PDF")
    return path


def _sample_pdf(resume: Resume) -> BinaryIO:
    # Seeded sample candidates have no file. Their résumé is built from the synthetic profile, in DEBUG only.
    if not settings.DEBUG:
        raise ResumeFileUnavailable("sample resumes are only served in DEBUG")
    lines = [
        f"{resume.display_name} (synthetic sample)",
        f"{resume.role} - {resume.years_experience} years",
        "Skills: " + ", ".join(resume.skills_json),
        resume.summary,
    ]
    return io.BytesIO(build_sample_pdf([line for line in lines if line]))


def open_resume_pdf(resume: Resume) -> BinaryIO:
    """Open the resume's PDF for streaming, or raise ResumeFileUnavailable."""
    if urlparse(resume.resume_uri).scheme == SAMPLE_SCHEME:
        return _sample_pdf(resume)
    path = _resolve_inside_root(resume.resume_uri)
    try:
        handle = path.open("rb")
    except OSError as error:
        raise ResumeFileUnavailable("file unreadable") from error
    if handle.read(len(PDF_MAGIC)) != PDF_MAGIC:
        handle.close()
        raise ResumeFileUnavailable("not a PDF")
    handle.seek(0)
    return handle
