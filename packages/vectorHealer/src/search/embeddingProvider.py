"""FastEmbed dense vector embedding inference provider with caching and fallback."""

import logging
import math
from typing import Dict, List, Optional, Tuple

from ..constants.healerConstants import (
    defaultVectorDimension,
    modelNameMiniLm,
)
from ..healerExceptions import (
    EmbeddingInferenceException,
)

logger = logging.getLogger(__name__)

# Which producer made a vector. Stamped onto substitution results so a similarity score computed
# from character hashes is never presented as a semantic match.
embeddingModeModel: str = "model"
embeddingModeHash: str = "hash"


class EmbeddingProvider:
    """Provides 384-dimensional dense vector embeddings with caching and cosine similarity."""

    def __init__(self, modelName: str = modelNameMiniLm) -> None:
        self.modelName = modelName
        self._embeddingCache: Dict[str, List[float]] = {}
        self._cachedMode: Dict[str, str] = {}
        self._fastembedModel: Optional[object] = None
        self._isFastembedInitialized = False

    def _normalizeVector(self, vector: List[float]) -> List[float]:
        """Scales vector to unit Euclidean length."""
        normSq = sum(val * val for val in vector)
        if normSq == 0:
            return vector
        magnitude = math.sqrt(normSq)
        return [val / magnitude for val in vector]

    def registerCachedVector(self, identifier: str, vector: List[float]) -> None:
        """Stores pre-computed normalized embedding vector into in-memory cache."""
        self._embeddingCache[identifier] = self._normalizeVector(vector)

    def computeCosineSimilarity(self, vectorA: List[float], vectorB: List[float]) -> float:
        """Computes mathematical cosine similarity between two float vectors."""
        if len(vectorA) != len(vectorB):
            raise EmbeddingInferenceException("Vector dimension mismatch for cosine similarity")
        dotProduct = sum(a * b for a, b in zip(vectorA, vectorB))
        normA = math.sqrt(sum(a * a for a in vectorA))
        normB = math.sqrt(sum(b * b for b in vectorB))
        if normA == 0 or normB == 0:
            return 0.0
        return dotProduct / (normA * normB)

    def _lazyInitFastEmbed(self) -> None:
        """Initializes fastembed model if available, and says so loudly when it is not.

        The model downloads from HuggingFace on first use and caches under $HOME, so this fails
        on an offline machine or a first run with no network. Swallowing that silently meant
        "cosine similarity" degraded to a hash of character codes with nothing in the output
        distinguishing the two modes -- the single highest-risk failure for a live demo, because
        it looks like it is working.
        """
        if self._isFastembedInitialized:
            return
        self._isFastembedInitialized = True
        try:
            from fastembed import TextEmbedding  # type: ignore

            self._fastembedModel = TextEmbedding(model_name=self.modelName)
        except Exception as initError:
            logger.warning(
                "fastembed model '%s' failed to load; falling back to character-hash "
                "pseudo-vectors, which are NOT semantically meaningful. Substitution results "
                "from this process are not real similarity matches: %s",
                self.modelName,
                initError,
            )
            self._fastembedModel = None

    def computeEmbedding(self, text: str) -> List[float]:
        """Generates a 384-dimensional dense embedding vector for input text.

        Callers that need to know whether the result is a real embedding should use
        `embedWithMode` instead; this returns only the vector, and a hash pseudo-vector is
        indistinguishable from a model output by inspection.
        """
        return self.embedWithMode(text)[0]

    def embedWithMode(self, text: str) -> Tuple[List[float], str]:
        """Returns the vector and which producer made it: 'model' or 'hash'.

        The mode travels with the vector so that a substitution result can be stamped with the
        producer that generated it. A dashboard showing "0.91 cosine similarity" computed from
        character hashes is worse than one showing nothing, because it invites belief.

        Mirrors packages/merchantApi/src/catalog/embeddingEngine.py, which already returns this
        pair on the auto-vectorizer path.
        """
        if not text or not text.strip():
            raise EmbeddingInferenceException("Input text cannot be empty for embedding inference")

        normalizedText = text.strip().lower()
        if normalizedText in self._embeddingCache:
            return self._embeddingCache[normalizedText], self._cachedMode.get(
                normalizedText, embeddingModeHash
            )

        self._lazyInitFastEmbed()
        if self._fastembedModel is not None:
            try:
                embeddingsGen = self._fastembedModel.embed([text])  # type: ignore
                denseList = list(next(iter(embeddingsGen)))
                normalizedVec = self._normalizeVector(denseList)
                self._embeddingCache[normalizedText] = normalizedVec
                self._cachedMode[normalizedText] = embeddingModeModel
                return normalizedVec, embeddingModeModel
            except Exception as err:
                raise EmbeddingInferenceException(f"FastEmbed inference failed: {err}")

        # Deterministic pseudo-embedding fallback when the fastembed model is unavailable. This
        # is a hash of character codes, not a semantic embedding: two texts that mean the same
        # thing land nowhere near each other. Returned with mode 'hash' so a caller can refuse
        # to present it as a similarity score.
        pseudoVector = [0.0] * defaultVectorDimension
        for index, char in enumerate(normalizedText):
            slot = (ord(char) * (index + 1) * 31) % defaultVectorDimension
            pseudoVector[slot] += 1.0
        normalizedFallback = self._normalizeVector(pseudoVector)
        self._embeddingCache[normalizedText] = normalizedFallback
        self._cachedMode[normalizedText] = embeddingModeHash
        return normalizedFallback, embeddingModeHash


__all__ = ["EmbeddingProvider", "embeddingModeHash", "embeddingModeModel"]
