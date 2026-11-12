"""Milvus collection schema, index and write/read helpers."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from matching.conf import MatchingSettings

_ID_RE = re.compile(r"^[0-9a-f]{16}$")  # resume_ids are generated hashes; validated before filter use


def get_client(settings: MatchingSettings) -> MilvusClient:
    from pymilvus import MilvusClient

    if not settings.milvus_uri.startswith(("http://", "https://")):
        Path(settings.milvus_uri).parent.mkdir(parents=True, exist_ok=True)  # Milvus Lite file
        return MilvusClient(uri=settings.milvus_uri)
    kwargs = {"uri": settings.milvus_uri}
    if settings.milvus_token:
        kwargs["token"] = settings.milvus_token
    if settings.milvus_db_name:
        kwargs["db_name"] = settings.milvus_db_name
    return MilvusClient(**kwargs)


@lru_cache(maxsize=1)
def get_shared_client() -> MilvusClient:
    """One client per process for the search API."""
    from matching.conf import get_matching_settings

    return get_client(get_matching_settings())


def search_chunks(client: MilvusClient, settings: MatchingSettings, vector: list[float], limit: int) -> list[dict]:
    """Nearest chunks to the query vector; each hit has 'distance' (cosine similarity) and 'entity'."""
    result = client.search(
        settings.collection,
        data=[vector],
        anns_field="dense_vec",
        limit=limit,
        output_fields=["resume_id", "section"],
        search_params={"metric_type": "COSINE"},
    )
    return list(result[0])


def ensure_collection(client: MilvusClient, settings: MatchingSettings, reset: bool = False) -> None:
    from pymilvus import DataType

    name = settings.collection
    if reset and client.has_collection(name):
        client.drop_collection(name)
    if client.has_collection(name):
        return

    # Phase 2 fields (skills, years_experience, ...) go in as dynamic fields.
    schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
    schema.add_field("chunk_id", DataType.VARCHAR, is_primary=True, max_length=64)  # {resume_id}:{idx}
    schema.add_field("resume_id", DataType.VARCHAR, max_length=16)
    schema.add_field("filename", DataType.VARCHAR, max_length=256)
    schema.add_field("section", DataType.VARCHAR, max_length=32)
    schema.add_field("text", DataType.VARCHAR, max_length=8192)
    schema.add_field("embed_model", DataType.VARCHAR, max_length=128)
    schema.add_field("dense_vec", DataType.FLOAT_VECTOR, dim=settings.embed_dim)

    index_params = client.prepare_index_params()
    params = {"M": 16, "efConstruction": 200} if settings.index_type == "HNSW" else {}
    index_params.add_index(
        field_name="dense_vec",
        index_type=settings.index_type,
        metric_type="COSINE",
        params=params,
    )
    client.create_collection(name, schema=schema, index_params=index_params)


def assert_model_compatible(client: MilvusClient, settings: MatchingSettings) -> None:
    """Refuse to mix vectors from different embedding models in one collection."""
    rows = client.query(settings.collection, filter="", output_fields=["embed_model"], limit=1)
    if rows and rows[0]["embed_model"] != settings.embed_model:
        raise RuntimeError(
            f"Collection built with '{rows[0]['embed_model']}', configured '{settings.embed_model}'. "
            "Re-run with --reset to rebuild."
        )


def resume_exists(client: MilvusClient, settings: MatchingSettings, resume_id: str) -> bool:
    if not _ID_RE.match(resume_id):
        raise ValueError("invalid resume_id")
    rows = client.query(
        settings.collection, filter=f'resume_id == "{resume_id}"', output_fields=["chunk_id"], limit=1
    )
    return bool(rows)


def upsert_chunks(client: MilvusClient, settings: MatchingSettings, rows: list[dict]) -> None:
    client.upsert(settings.collection, data=rows)
