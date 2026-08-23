"""FastEmbed dense vector embedding inference provider with caching and fallback."""

import math
from typing import Dict, List, Optional
from razoragentMesh.packages.vectorHealer.healerConstants import (
    defaultVectorDimension,
    modelNameMiniLm,
)
from razoragentMesh.packages.vectorHealer.healerExceptions import (
    EmbeddingInferenceException,
)


class EmbeddingProvider:
    """Provides 384-dimensional dense vector embeddings with caching and cosine similarity."""

    def __init__(self, modelName: str = modelNameMiniLm) -> None:
        self.modelName = modelName
        self._embeddingCache: Dict[str, List[float]] = {}
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
        """Initializes fastembed model if available in local environment."""
        if self._isFastembedInitialized:
            return
        self._isFastembedInitialized = True
        try:
            from fastembed import TextEmbedding  # type: ignore

            self._fastembedModel = TextEmbedding(model_name=self.modelName)
        except Exception:
            self._fastembedModel = None

    def computeEmbedding(self, text: str) -> List[float]:
        """Generates 384-dimensional dense embedding vector for input text."""
        if not text or not text.strip():
            raise EmbeddingInferenceException("Input text cannot be empty for embedding inference")

        normalizedText = text.strip().lower()
        if normalizedText in self._embeddingCache:
            return self._embeddingCache[normalizedText]

        self._lazyInitFastEmbed()
        if self._fastembedModel is not None:
            try:
                embeddingsGen = self._fastembedModel.embed([text])  # type: ignore
                denseList = list(next(iter(embeddingsGen)))
                normalizedVec = self._normalizeVector(denseList)
                self._embeddingCache[normalizedText] = normalizedVec
                return normalizedVec
            except Exception as err:
                raise EmbeddingInferenceException(f"FastEmbed inference failed: {err}")

        # Deterministic pseudo-embedding fallback when fastembed model is offline
        pseudoVector = [0.0] * defaultVectorDimension
        for index, char in enumerate(normalizedText):
            slot = (ord(char) * (index + 1) * 31) % defaultVectorDimension
            pseudoVector[slot] += 1.0
        normalizedFallback = self._normalizeVector(pseudoVector)
        self._embeddingCache[normalizedText] = normalizedFallback
        return normalizedFallback
