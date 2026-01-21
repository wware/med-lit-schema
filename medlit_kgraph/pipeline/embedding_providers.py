"""Embedding provider implementations for medical literature domain.

Provides implementations of kgraph's EmbeddingGeneratorInterface using
various embedding models (Ollama, sentence-transformers, etc.).
"""

from typing import Sequence, Optional, Any
import hashlib

from kgraph.pipeline.embedding import EmbeddingGeneratorInterface

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class OllamaEmbeddingGenerator(EmbeddingGeneratorInterface):
    """Ollama-based embedding generator.

    Uses Ollama's embedding API for generating semantic embeddings.
    Supports models like nomic-embed-text, all-minilm, etc.
    """

    def __init__(
        self,
        model_name: str = "nomic-embed-text",
        host: str = "http://localhost:11434",
        timeout: float = 60.0,
    ):
        """Initialize Ollama embedding generator.

        Args:
            model_name: Ollama embedding model name
            host: Ollama server URL
            timeout: Request timeout in seconds
        """
        if not OLLAMA_AVAILABLE:
            raise ImportError("ollama package not installed. Install with: pip install ollama")

        self._model_name = model_name
        self._client = ollama.Client(host=host, timeout=timeout)

        # Known embedding dimensions for common models
        KNOWN_DIMENSIONS = {
            "nomic-embed-text": 768,
            "nomic-embed-text-v1": 768,
            "all-minilm": 384,
            "all-mpnet-base-v2": 768,
        }

        # Determine embedding dimension by encoding a dummy string
        try:
            dummy_embedding = self._client.embed(model=self._model_name, input="dummy text")
            self._embedding_dim = len(dummy_embedding["embeddings"][0])
        except Exception as e:
            # Fallback to known dimensions if connection fails
            if model_name in KNOWN_DIMENSIONS:
                self._embedding_dim = KNOWN_DIMENSIONS[model_name]
                print(f"Warning: Could not connect to Ollama at {host} to determine embedding dimension.")
                print(f"Using known dimension {self._embedding_dim} for model '{model_name}'.")
            else:
                raise RuntimeError(
                    f"Failed to get embedding dimension from Ollama model '{model_name}'. "
                    f"Ensure the model is pulled and Ollama is running at {host}. Error: {e}"
                )

    @property
    def dimension(self) -> int:
        return self._embedding_dim

    async def generate(self, text: str) -> tuple[float, ...]:
        """Generate embedding for a single text."""
        response = self._client.embed(model=self._model_name, input=text)
        return tuple(response["embeddings"][0])

    async def generate_batch(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        """Generate embeddings for multiple texts in batch."""
        responses = self._client.embed(model=self._model_name, input=list(texts))
        return [tuple(emb) for emb in responses["embeddings"]]


class SentenceTransformerEmbeddingGenerator(EmbeddingGeneratorInterface):
    """Sentence Transformers embedding generator.

    Uses sentence-transformers library for local embedding generation.
    Supports models like all-MiniLM-L6-v2, all-mpnet-base-v2, etc.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: Optional[str] = None,
    ):
        """Initialize Sentence Transformers embedding generator.

        Args:
            model_name: HuggingFace model name or path
            device: Device to use ("cpu", "cuda", etc.). None = auto-detect.
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers not installed. Install with: pip install sentence-transformers"
            )

        self._model_name = model_name
        self._model = SentenceTransformer(model_name, device=device)
        self._embedding_dim = self._model.get_sentence_embedding_dimension()

    @property
    def dimension(self) -> int:
        return self._embedding_dim

    async def generate(self, text: str) -> tuple[float, ...]:
        """Generate embedding for a single text."""
        embedding = self._model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return tuple(embedding.tolist())

    async def generate_batch(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        """Generate embeddings for multiple texts in batch."""
        embeddings = self._model.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )
        return [tuple(emb.tolist()) for emb in embeddings]


class HashEmbeddingGenerator(EmbeddingGeneratorInterface):
    """Simple hash-based embedding generator (fallback/placeholder).

    This is a deterministic but non-semantic embedding generator.
    Useful for testing or when no embedding model is available.
    """

    def __init__(self, dimension: int = 32):
        """Initialize hash-based embedding generator.

        Args:
            dimension: Embedding dimension (default: 32)
        """
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def generate(self, text: str) -> tuple[float, ...]:
        """Generate hash-based embedding."""
        h = hashlib.sha256(text.lower().encode("utf-8")).digest()
        values = [b / 255.0 for b in h[: self._dimension]]
        mag = sum(v * v for v in values) ** 0.5
        if mag == 0:
            return tuple(0.0 for _ in range(self._dimension))
        return tuple(v / mag for v in values)

    async def generate_batch(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        """Generate hash-based embeddings for multiple texts."""
        return [await self.generate(t) for t in texts]


def create_embedding_generator(
    provider: str = "hash",
    **kwargs: Any,
) -> EmbeddingGeneratorInterface:
    """Factory function to create an embedding generator.

    Args:
        provider: Provider name ("ollama", "sentence-transformers", or "hash")
        **kwargs: Provider-specific arguments

    Returns:
        EmbeddingGeneratorInterface instance

    Examples:
        >>> embedder = create_embedding_generator("ollama", model_name="nomic-embed-text")
        >>> embedder = create_embedding_generator("sentence-transformers", model_name="all-MiniLM-L6-v2")
        >>> embedder = create_embedding_generator("hash", dimension=32)
    """
    if provider.lower() == "ollama":
        return OllamaEmbeddingGenerator(**kwargs)
    elif provider.lower() == "sentence-transformers":
        return SentenceTransformerEmbeddingGenerator(**kwargs)
    elif provider.lower() == "hash":
        return HashEmbeddingGenerator(**kwargs)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}. Use 'ollama', 'sentence-transformers', or 'hash'")
