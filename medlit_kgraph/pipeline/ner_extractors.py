"""NER extractor implementations for medical entity extraction.

Provides implementations using BioBERT, scispaCy, and Ollama LLM.
"""

from abc import ABC, abstractmethod
from typing import Any
import re

from kgraph.entity import EntityMention

try:
    from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

from .llm_client import LLMClientInterface, create_llm_client

# Stopwords for entity filtering
STOPWORDS = frozenset({
    "the", "and", "or", "but", "with", "from", "that", "this",
    "these", "those", "their", "there", "a", "an", "as", "at",
})


class NERExtractorInterface(ABC):
    """Abstract interface for NER extractors."""

    @abstractmethod
    def extract_entities(self, text: str) -> list[dict[str, Any]]:
        """Extract entities from text.

        Args:
            text: Text to extract entities from

        Returns:
            List of dicts with keys:
            - "word": entity text
            - "entity_group": entity type (e.g., "Disease", "Gene")
            - "score": confidence (0.0-1.0)
            - "start": start offset (optional)
            - "end": end offset (optional)
        """


class BioBERTNERExtractor(NERExtractorInterface):
    """BioBERT-based NER extractor for biomedical entities.

    Uses the BioBERT model fine-tuned for biomedical NER.
    """

    def __init__(
        self,
        model_name: str = "dmis-lab/biobert-v1.1",
        device: int = -1,  # -1 = CPU, 0+ = GPU
    ):
        """Initialize BioBERT NER extractor.

        Args:
            model_name: HuggingFace model name
            device: Device ID (-1 for CPU, 0+ for GPU)
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers not installed. Install with: pip install transformers")

        self._pipeline = pipeline(
            "ner",
            model=model_name,
            tokenizer=model_name,
            aggregation_strategy="simple",
            device=device,
        )

    def extract_entities(self, text: str) -> list[dict[str, Any]]:
        """Extract entities using BioBERT."""
        if not text or len(text.strip()) < 10:
            return []

        results = self._pipeline(text)
        entities = []

        for ent in results:
            # BioBERT typically returns entities with "entity_group" or "label"
            label = ent.get("entity_group", ent.get("label", "O"))
            if label == "O":
                continue

            # Map BioBERT labels to our entity types
            entity_type = self._map_label_to_entity_type(label)

            entities.append({
                "word": ent["word"].strip(),
                "entity_group": entity_type,
                "score": float(ent.get("score", 0.0)),
                "start": ent.get("start", 0),
                "end": ent.get("end", 0),
            })

        return entities

    def _map_label_to_entity_type(self, label: str) -> str:
        """Map BioBERT label to entity type."""
        # BioBERT labels vary by model; adjust as needed
        label_upper = label.upper()
        if "DISEASE" in label_upper or "DISEASE" in label_upper:
            return "disease"
        elif "GENE" in label_upper or "PROTEIN" in label_upper:
            return "gene"  # Could be "protein" too, but gene is more common
        elif "DRUG" in label_upper or "CHEMICAL" in label_upper:
            return "drug"
        else:
            return "disease"  # Default fallback


class SciSpaCyNERExtractor(NERExtractorInterface):
    """scispaCy-based NER extractor for biomedical entities.

    Uses scispaCy models (e.g., en_ner_bc5cdr_md) for fast NER.
    """

    def __init__(self, model_name: str = "en_ner_bc5cdr_md"):
        """Initialize scispaCy NER extractor.

        Args:
            model_name: scispaCy model name
        """
        if not SPACY_AVAILABLE:
            raise ImportError("spacy not installed. Install with: pip install spacy")
        try:
            self._nlp = spacy.load(model_name)
        except OSError:
            raise ImportError(
                f"scispaCy model '{model_name}' not found. "
                f"Install with: python -m spacy download {model_name}"
            )

    def extract_entities(self, text: str) -> list[dict[str, Any]]:
        """Extract entities using scispaCy."""
        if not text or len(text.strip()) < 10:
            return []

        doc = self._nlp(text)
        entities = []

        for ent in doc.ents:
            # scispaCy entities have .label_ property
            entity_type = self._map_label_to_entity_type(ent.label_)

            entities.append({
                "word": ent.text.strip(),
                "entity_group": entity_type,
                "score": 0.9,  # scispaCy doesn't provide confidence scores
                "start": ent.start_char,
                "end": ent.end_char,
            })

        return entities

    def _map_label_to_entity_type(self, label: str) -> str:
        """Map scispaCy label to entity type."""
        label_upper = label.upper()
        if "DISEASE" in label_upper or "CONDITION" in label_upper:
            return "disease"
        elif "CHEMICAL" in label_upper or "DRUG" in label_upper:
            return "drug"
        else:
            return "disease"  # Default fallback


class OllamaNERExtractor(NERExtractorInterface):
    """Ollama LLM-based NER extractor.

    Uses an LLM to extract entities via prompting.
    """

    OLLAMA_NER_PROMPT = """Extract all disease and medical condition entities from the following text.
Return ONLY a JSON array of objects with "entity" (the disease name) and "confidence" (0.0-1.0) fields.
Do not include any explanation, just the JSON array.

Example output:
[{{"entity": "diabetes", "confidence": 0.95}}, {{"entity": "hypertension", "confidence": 0.90}}]

If no diseases are found, return an empty array: []

Text to analyze:
{text}

JSON output:"""

    def __init__(
        self,
        llm_client: LLMClientInterface | None = None,
        model: str = "llama3.1:8b",
        host: str = "http://localhost:11434",
    ):
        """Initialize Ollama NER extractor.

        Args:
            llm_client: Optional LLM client (if None, creates Ollama client)
            model: Ollama model name
            host: Ollama server URL
        """
        if llm_client is None:
            from .llm_client import OllamaLLMClient
            self._llm = OllamaLLMClient(model=model, host=host)
        else:
            self._llm = llm_client

    def extract_entities(self, text: str) -> list[dict[str, Any]]:
        """Extract entities using Ollama LLM."""
        if not text or len(text.strip()) < 10:
            return []

        # Use larger text chunks (8000 chars) for better efficiency
        prompt = self.OLLAMA_NER_PROMPT.format(text=text[:8000])

        try:
            import asyncio
            # Run async method in sync context
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            response = loop.run_until_complete(self._llm.generate_json(prompt))

            entities = []
            if isinstance(response, list):
                for item in response:
                    if isinstance(item, dict):
                        entity_name = item.get("entity", "").strip()
                        confidence = float(item.get("confidence", 0.5))

                        # Basic hygiene filters
                        if len(entity_name) < 3:
                            continue
                        if entity_name.lower() in STOPWORDS:
                            continue
                        if confidence < 0.5:
                            continue

                        entities.append({
                            "word": entity_name,
                            "entity_group": "disease",  # Ollama prompt focuses on diseases
                            "score": confidence,
                            "start": 0,  # Unknown from LLM
                            "end": 0,
                        })

            return entities

        except Exception as e:
            print(f"Warning: Ollama NER extraction failed: {e}")
            return []


def create_ner_extractor(
    provider: str = "biobert",
    **kwargs: Any,
) -> NERExtractorInterface:
    """Factory function to create an NER extractor.

    Args:
        provider: Provider name ("biobert", "scispacy", or "ollama")
        **kwargs: Provider-specific arguments

    Returns:
        NERExtractorInterface instance

    Examples:
        >>> extractor = create_ner_extractor("biobert")
        >>> extractor = create_ner_extractor("scispacy", model_name="en_ner_bc5cdr_md")
        >>> extractor = create_ner_extractor("ollama", model="llama3.1:8b")
    """
    if provider.lower() == "biobert":
        return BioBERTNERExtractor(**kwargs)
    elif provider.lower() == "scispacy":
        return SciSpaCyNERExtractor(**kwargs)
    elif provider.lower() == "ollama":
        return OllamaNERExtractor(**kwargs)
    else:
        raise ValueError(f"Unknown NER provider: {provider}. Use 'biobert', 'scispacy', or 'ollama'")
