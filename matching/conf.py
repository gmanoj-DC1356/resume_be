"""Environment-driven settings for the matching engine. No secrets live here."""
import os
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings as django_settings


@dataclass(frozen=True)
class MatchingSettings:
    # Connection: a file path => Milvus Lite; http(s)://host:19530 => Milvus Standalone/Cluster.
    # NOTE: do not name these MILVUS_URI/MILVUS_TOKEN - pymilvus parses MILVUS_URI itself on import
    # and rejects file paths, so we use a MATCHING_ prefix.
    milvus_uri: str = os.environ.get(
        "MATCHING_MILVUS_URI", str(Path(django_settings.BASE_DIR) / "data" / "milvus_resumes.db")
    )
    milvus_token: str = os.environ.get("MATCHING_MILVUS_TOKEN", "")  # secret: .env / secrets manager only
    milvus_db_name: str = os.environ.get("MATCHING_MILVUS_DB_NAME", "")  # empty => server default database
    collection: str = os.environ.get("MATCHING_MILVUS_COLLECTION", "resume_chunks")
    embed_model: str = os.environ.get("EMBED_MODEL", "BAAI/bge-large-en-v1.5")
    embed_dim: int = int(os.environ.get("EMBED_DIM", "1024"))  # must match the model's output size
    # BGE models want this prefix on queries only, never on documents.
    query_prefix: str = os.environ.get(
        "EMBED_QUERY_PREFIX", "Represent this sentence for searching relevant passages: "
    )
    # FLAT = exact search (fine for small local corpora). Use HNSW on Milvus Standalone.
    index_type: str = os.environ.get("MILVUS_INDEX_TYPE", "FLAT")
    chunk_words: int = int(os.environ.get("CHUNK_WORDS", "300"))
    chunk_overlap_words: int = int(os.environ.get("CHUNK_OVERLAP_WORDS", "40"))
    max_pdf_bytes: int = int(os.environ.get("MAX_PDF_BYTES", str(10 * 1024 * 1024)))
    max_pdf_pages: int = int(os.environ.get("MAX_PDF_PAGES", "20"))
    embed_batch_size: int = int(os.environ.get("EMBED_BATCH_SIZE", "32"))
    # Search / scoring. Starting values, to be tuned against labelled data (Phase 6).
    search_top_chunks: int = int(os.environ.get("SEARCH_TOP_CHUNKS", "50"))
    semantic_floor: float = float(os.environ.get("SEMANTIC_FLOOR", "0.5"))  # cosine below this scores 0
    weight_skills: float = float(os.environ.get("SCORE_WEIGHT_SKILLS", "0.6"))
    weight_semantic: float = float(os.environ.get("SCORE_WEIGHT_SEMANTIC", "0.4"))


def get_matching_settings() -> MatchingSettings:
    return MatchingSettings()


def search_mode() -> str:
    """'sample' = seeded database rows (default for now); 'vector' = Milvus semantic search."""
    mode = os.environ.get("MATCHING_SEARCH_MODE", "sample")
    return mode if mode in ("sample", "vector") else "sample"
