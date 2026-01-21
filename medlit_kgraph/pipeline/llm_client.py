"""LLM client abstraction layer for entity and relationship extraction.

Provides a unified interface for different LLM providers (Ollama, OpenAI, etc.)
to enable flexible extraction strategies.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
import json
import re

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class LLMClientInterface(ABC):
    """Abstract interface for LLM clients."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text completion from a prompt.

        Args:
            prompt: The input prompt text.
            temperature: Sampling temperature (0.0-2.0). Lower = more deterministic.
            max_tokens: Maximum tokens to generate (None = model default).

        Returns:
            Generated text response.
        """

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.1,
    ) -> dict[str, Any] | list[Any]:
        """Generate structured JSON response from a prompt.

        Args:
            prompt: The input prompt text (should request JSON output).
            temperature: Sampling temperature (0.0-2.0).

        Returns:
            Parsed JSON object (dict or list).

        Raises:
            ValueError: If response is not valid JSON.
        """


class OllamaLLMClient(LLMClientInterface):
    """Ollama LLM client implementation."""

    def __init__(
        self,
        model: str = "llama3.1:8b",
        host: str = "http://localhost:11434",
        timeout: float = 300.0,
    ):
        """Initialize Ollama client.

        Args:
            model: Ollama model name (e.g., "llama3.1:8b", "meditron:70b")
            host: Ollama server URL
            timeout: Request timeout in seconds
        """
        if not OLLAMA_AVAILABLE:
            raise ImportError("ollama package not installed. Install with: pip install ollama")

        self.model = model
        self.host = host
        self._client = ollama.Client(host=host, timeout=timeout)

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text using Ollama."""
        options: dict[str, Any] = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens

        response = self._client.generate(
            model=self.model,
            prompt=prompt,
            options=options,
        )
        return response.get("response", "").strip()

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.1,
    ) -> dict[str, Any] | list[Any]:
        """Generate JSON using Ollama."""
        response_text = await self.generate(prompt, temperature)

        # Try to extract JSON from response (LLMs sometimes add extra text)
        json_start = response_text.find("[")
        json_end = response_text.rfind("]") + 1
        if json_start == -1:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

        if json_start == -1:
            raise ValueError(f"No JSON found in response: {response_text[:200]}")

        json_text = response_text[json_start:json_end]
        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in response: {e}\nResponse: {json_text[:500]}")


class OpenAILLMClient(LLMClientInterface):
    """OpenAI LLM client implementation."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """Initialize OpenAI client.

        Args:
            model: OpenAI model name (e.g., "gpt-4o-mini", "gpt-4o")
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            base_url: Custom base URL (for OpenAI-compatible APIs)
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package not installed. Install with: pip install openai")

        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text using OpenAI."""
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.1,
    ) -> dict[str, Any] | list[Any]:
        """Generate JSON using OpenAI (with JSON mode)."""
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that returns valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            response_format={"type": "json_object"} if "{" in prompt else None,
        )
        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in response: {e}\nResponse: {content[:500]}")


def create_llm_client(
    provider: str = "ollama",
    **kwargs: Any,
) -> LLMClientInterface:
    """Factory function to create an LLM client.

    Args:
        provider: Provider name ("ollama" or "openai")
        **kwargs: Provider-specific arguments

    Returns:
        LLMClientInterface instance

    Examples:
        >>> client = create_llm_client("ollama", model="llama3.1:8b")
        >>> client = create_llm_client("openai", model="gpt-4o-mini", api_key="...")
    """
    if provider.lower() == "ollama":
        return OllamaLLMClient(**kwargs)
    elif provider.lower() == "openai":
        return OpenAILLMClient(**kwargs)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Use 'ollama' or 'openai'")
