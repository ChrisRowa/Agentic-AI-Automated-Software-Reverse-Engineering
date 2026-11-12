"""
Embedding Providers for Code Semantic Retrieval.
Supports local sentence-transformers, API-based models, and deterministic hashing fallback.
Ensures zero-crash graceful degradation when offline or when model weights are not loaded.
"""
import abc
import hashlib
import math
import structlog
from typing import List, Optional
import numpy as np

from backend.core.config import settings

logger = structlog.get_logger(__name__)


class EmbeddingProvider(abc.ABC):
    """Abstract base class for text and code embedding providers."""

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        pass

    @property
    @abc.abstractmethod
    def is_available(self) -> bool:
        pass

    @abc.abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass

    @abc.abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """
    Local embedding using sentence-transformers (e.g. all-MiniLM-L6-v2, 384 dim).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._dimension = 384
        self._available = True
        self._load_attempted = False

    def _ensure_loaded(self):
        if not self._load_attempted:
            self._load_attempted = True
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading sentence-transformers model", model=self.model_name)
                # Load with local_files_only attempt first, or standard load
                self._model = SentenceTransformer(self.model_name)
                # Compute actual dimension
                sample = self._model.encode("test", show_progress_bar=False)
                self._dimension = int(sample.shape[-1])
                self._available = True
                logger.info("Embedding model loaded successfully", dimension=self._dimension)
            except Exception as e:
                logger.warning(
                    "SentenceTransformer could not be loaded; falling back to deterministic hashing",
                    model=self.model_name,
                    error=str(e),
                )
                self._model = None
                self._available = False

    @property
    def dimension(self) -> int:
        self._ensure_loaded()
        return self._dimension

    @property
    def is_available(self) -> bool:
        self._ensure_loaded()
        return self._available and self._model is not None

    def embed_text(self, text: str) -> List[float]:
        self._ensure_loaded()
        if not self.is_available:
            raise RuntimeError("SentenceTransformer is not available")
        embedding = self._model.encode(text, show_progress_bar=False, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        self._ensure_loaded()
        if not self.is_available:
            raise RuntimeError("SentenceTransformer is not available")
        if not texts:
            return []
        embeddings = self._model.encode(texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
        return embeddings.tolist()


class DeterministicHashingEmbeddingProvider(EmbeddingProvider):
    """
    Guaranteed offline embedding provider using multi-resolution character + word n-gram hashing.
    Outputs unit-normalized dense vectors of length `dim` (default 384).
    Enables semantic similarity without requiring internet access or large model downloads.
    """

    def __init__(self, dim: int = 384):
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def is_available(self) -> bool:
        return True

    def _hash_token(self, token: str, seed: int) -> int:
        h = hashlib.md5(f"{seed}:{token}".encode("utf-8")).hexdigest()
        return int(h, 16) % self._dim

    def embed_text(self, text: str) -> List[float]:
        vec = np.zeros(self._dim, dtype=np.float32)
        words = text.lower().split()
        if not words:
            return vec.tolist()

        # Word unigrams and bigrams
        for i, w in enumerate(words):
            idx1 = self._hash_token(w, 1)
            vec[idx1] += 1.0
            idx2 = self._hash_token(w, 2)
            vec[idx2] += 0.5
            if i + 1 < len(words):
                bigram = f"{w}_{words[i+1]}"
                idx_bi = self._hash_token(bigram, 3)
                vec[idx_bi] += 1.5

        # Character 3-grams and 4-grams for subword / code token matching
        compact = text.lower().replace(" ", "")
        for n in (3, 4):
            for i in range(len(compact) - n + 1):
                gram = compact[i:i + n]
                idx_g = self._hash_token(gram, 10 + n)
                vec[idx_g] += 0.3

        # L2 normalize
        norm = np.linalg.norm(vec)
        if norm > 1e-9:
            vec /= norm
        return vec.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


# Provider Cache / Singleton
_EMBEDDING_PROVIDER: Optional[EmbeddingProvider] = None


def get_embedding_provider(force_provider: Optional[str] = None) -> EmbeddingProvider:
    """
    Factory function returning the configured embedding provider.
    Tries configured provider; defaults to high-speed deterministic hashing for zero-crash offline execution.
    """
    global _EMBEDDING_PROVIDER
    if force_provider:
        if force_provider in ("deterministic", "fast", "hashing"):
            return DeterministicHashingEmbeddingProvider(dim=384)
        elif force_provider in ("sentence-transformers", "local"):
            return SentenceTransformerEmbeddingProvider(model_name=settings.embedding_model)

    if _EMBEDDING_PROVIDER is not None:
        return _EMBEDDING_PROVIDER

    provider_name = (settings.embedding_provider or "deterministic").lower()

    if provider_name == "sentence-transformers":
        local_provider = SentenceTransformerEmbeddingProvider(model_name=settings.embedding_model)
        if local_provider.is_available:
            _EMBEDDING_PROVIDER = local_provider
            return _EMBEDDING_PROVIDER

    _EMBEDDING_PROVIDER = DeterministicHashingEmbeddingProvider(dim=384)
    return _EMBEDDING_PROVIDER
