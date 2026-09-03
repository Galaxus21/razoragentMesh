"""384-dimensional dense embedding engine with a deterministic character-hash fallback."""

import logging
import math
from typing import Dict, List, Optional

from ..constants.merchantConstants import (
    defaultVectorDimension, embeddingModeHash, embeddingModeModel, modelNameMiniLm,
)

logger = logging.getLogger(__name__)


class _EmbeddingEngine:
    """Provides 384-dimensional dense vector embeddings with fallback."""

    def __init__(self, modelName: str = modelNameMiniLm) -> None:
        self.modelName = modelName
        self._cache: Dict[str, tuple[List[float], str]] = {}
        self._fastembedModel: Optional[object] = None
        self._isInitialized = False

    def _normalize(self, vector: List[float]) -> List[float]:
        normSq = sum(v * v for v in vector)
        return vector if normSq == 0.0 else [v / math.sqrt(normSq) for v in vector]

    def _initModel(self) -> None:
        if not self._isInitialized:
            self._isInitialized = True
            try:
                from fastembed import TextEmbedding  # type: ignore

                self._fastembedModel = TextEmbedding(model_name=self.modelName)
            except Exception as err:
                # Names the subsystem that actually failed. This previously logged
                # "Qdrant unavailable", which sent readers to the wrong service entirely --
                # and at INFO, where a silent downgrade to hash similarity does not belong.
                logger.warning(
                    "fastembed model '%s' failed to load; falling back to character-hash "
                    "pseudo-vectors, which are NOT semantically meaningful: %s",
                    self.modelName,
                    err,
                )
                self._fastembedModel = None

    def embedWithMode(self, text: str) -> tuple[List[float], str]:
        """Returns the vector and which producer made it: 'model' or 'hash'.

        Callers need this because the two are indistinguishable by inspection, and cosine
        similarity over a character hash is meaningless for language. Anything presenting
        results to a user must be able to say which one ran.
        """
        cleaned = text.strip().lower()
        cached = self._cache.get(cleaned)
        if cached is not None:
            return cached

        self._initModel()
        if self._fastembedModel is not None:
            try:
                gen = self._fastembedModel.embed([text])  # type: ignore
                vec = list(next(iter(gen)))
                normalized = self._normalize(vec)
                self._cache[cleaned] = (normalized, embeddingModeModel)
                return self._cache[cleaned]
            except Exception as err:
                logger.warning(
                    "fastembed inference failed; falling back to character-hash "
                    "pseudo-vectors, which are NOT semantically meaningful: %s",
                    err,
                )

        # Deterministic 384-dim pseudo-vector fallback for offline environments
        pseudo = [0.0] * defaultVectorDimension
        for idx, char in enumerate(cleaned):
            slot = (ord(char) * (idx + 1) * 31) % defaultVectorDimension
            pseudo[slot] += 1.0
        normalizedFallback = self._normalize(pseudo)
        self._cache[cleaned] = (normalizedFallback, embeddingModeHash)
        return self._cache[cleaned]

    def embed(self, text: str) -> List[float]:
        """Vector only. Prefer embedWithMode where the caller reports provenance."""
        vector, _mode = self.embedWithMode(text)
        return vector


__all__ = [
    "_EmbeddingEngine",
]
