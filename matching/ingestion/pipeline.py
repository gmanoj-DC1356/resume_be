"""Folder of PDFs -> chunks -> embeddings -> Milvus."""
import logging
from dataclasses import dataclass, field
from pathlib import Path

from matching.conf import MatchingSettings
from matching.embedding.embedder import Embedder
from matching.ingestion.chunker import chunk_text
from matching.ingestion.pdf_loader import iter_pdf_paths, load_pdf
from matching.ingestion.resume_parser import parse_resume
from matching.store import milvus_store
from resumes.models import Resume

logger = logging.getLogger(__name__)


@dataclass
class IngestReport:
    ingested: int = 0
    skipped_existing: int = 0
    failed: list[str] = field(default_factory=list)
    chunks: int = 0


def ingest_folder(input_dir: Path, settings: MatchingSettings, reset: bool = False) -> IngestReport:
    client = milvus_store.get_client(settings)
    milvus_store.ensure_collection(client, settings, reset=reset)
    milvus_store.assert_model_compatible(client, settings)
    embedder = Embedder(settings)
    report = IngestReport()

    for path in iter_pdf_paths(input_dir, settings.max_pdf_bytes):
        try:
            pdf = load_pdf(path, settings.max_pdf_pages)
            parsed = parse_resume(pdf.text)
            Resume.objects.update_or_create(
                candidate_ref=pdf.resume_id,
                defaults={
                    "resume_uri": path.resolve().as_uri(),
                    "display_name": parsed.name,
                    "role": parsed.role,
                    "years_experience": parsed.years_experience,
                    "skills_json": parsed.skills,
                    "summary": parsed.summary,
                },
            )
            if milvus_store.resume_exists(client, settings, pdf.resume_id):
                report.skipped_existing += 1
                continue
            chunks = chunk_text(pdf.text, settings.chunk_words, settings.chunk_overlap_words)
            vectors = embedder.embed_documents([c.text for c in chunks])
            rows = [
                {
                    "chunk_id": f"{pdf.resume_id}:{c.chunk_idx}",
                    "resume_id": pdf.resume_id,
                    "filename": pdf.filename[:256],
                    "section": c.section,
                    "text": c.text[:8192],
                    "embed_model": embedder.model_name,
                    "dense_vec": v,
                }
                for c, v in zip(chunks, vectors)
            ]
            milvus_store.upsert_chunks(client, settings, rows)
            report.ingested += 1
            report.chunks += len(rows)
        except Exception as exc:  # one bad file must not stop the run; never log resume text
            logger.error("Failed %s: %s", path.name, exc)
            report.failed.append(path.name)
    return report
