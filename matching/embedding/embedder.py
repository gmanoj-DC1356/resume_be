"""Single embedder used for BOTH ingestion and queries so vectors stay comparable."""
from functools import lru_cache

from matching.conf import MatchingSettings, get_matching_settings


class Embedder:
    def __init__(self, settings: MatchingSettings):
        from sentence_transformers import SentenceTransformer  # lazy: heavy import

        self._settings = settings
        self._model = SentenceTransformer(settings.embed_model)
        dim = self._model.get_sentence_embedding_dimension()
        if dim != settings.embed_dim:
            raise ValueError(f"Model dim {dim} != configured EMBED_DIM {settings.embed_dim}")

    @property
    def model_name(self) -> str:
        return self._settings.embed_model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            batch_size=self._settings.embed_batch_size,
            normalize_embeddings=True,  # L2-normalised, matches COSINE metric
        )
        return vectors.tolist()

    def embed_query(self, query: str) -> list[float]:
        vector = self._model.encode(self._settings.query_prefix + query, normalize_embeddings=True)
        return vector.tolist()


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """Load the model once per process (loading is slow); used by the search API."""
    return Embedder(get_matching_settings())
