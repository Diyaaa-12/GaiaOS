"""EmbeddingProvider abstraction and concrete implementations."""

from __future__ import annotations

import hashlib
import random
from abc import ABC, abstractmethod

import httpx

from config.settings import Settings


class EmbeddingProvider(ABC):
    """Abstract base class for generating text embeddings.

    Ensures loose coupling between orchestration logic and specific embedding APIs.
    """

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Generate a vector embedding for a query string."""
        pass

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a list of document chunks."""
        pass


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic offline mock embedding provider.

    Generates pseudo-random unit vectors of configured dimensions using text hashes,
    allowing reproducible tests and offline local development.
    """

    def __init__(self, dimension: int = 1536, should_fail: bool = False) -> None:
        self.dimension = dimension
        self.should_fail = should_fail

    async def embed_query(self, text: str) -> list[float]:
        if self.should_fail:
            raise RuntimeError("Embedding service unreachable")
        return self._generate_vector(text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self.should_fail:
            raise RuntimeError("Embedding service unreachable")
        return [self._generate_vector(t) for t in texts]

    def _generate_vector(self, text: str) -> list[float]:
        # Generate hash of query to seed deterministic values
        hasher = hashlib.sha256(text.encode("utf-8"))
        digest = hasher.digest()
        seed = int.from_bytes(digest, byteorder="big")
        
        rng = random.Random(seed)
        vec = [rng.uniform(-1.0, 1.0) for _ in range(self.dimension)]
        
        # Normalize to unit length for clean cosine similarity
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Real HTTP client wrapping OpenAI's embedding API.

    Uses httpx directly to avoid heavy third-party SDK dependencies.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.dimension = dimension

    async def embed_query(self, text: str) -> list[float]:
        res = await self._embed([text])
        return res[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts)

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": texts,
            "model": self.model,
            "dimensions": self.dimension,
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    json=payload,
                    headers=headers,
                    timeout=10.0,
                )
                if response.status_code != 200:
                    raise RuntimeError(f"OpenAI API error: {response.text}")
                data = response.json()
                return [item["embedding"] for item in data["data"]]
            except Exception as e:
                raise RuntimeError(f"Embedding service unreachable: {str(e)}") from e


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Dependency injection factory resolver for the active EmbeddingProvider."""
    # If a simulation environment variable for failure is set, trigger mock failure
    import os
    if os.environ.get("SIMULATE_EMBEDDING_FAILURE") == "true":
        return MockEmbeddingProvider(
            dimension=settings.embedding_dimension,
            should_fail=True,
        )

    if settings.embedding_api_key:
        return OpenAIEmbeddingProvider(
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )
    return MockEmbeddingProvider(dimension=settings.embedding_dimension)
