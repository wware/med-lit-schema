# Extraction Logic Porting Summary

This document summarizes the porting of extraction logic from `med-lit-schema/ingest/` to `medlit_kgraph/pipeline/`.

## Completed Porting

### 1. LLM Client Abstraction Layer

**File**: `pipeline/llm_client.py`

- Created `LLMClientInterface` abstract base class
- Implemented `OllamaLLMClient` for local/remote Ollama servers
- Implemented `OpenAILLMClient` for OpenAI API
- Factory function `create_llm_client()` for easy instantiation
- Supports both text generation and structured JSON generation

**Usage**:
```python
from medlit_kgraph.pipeline.llm_client import create_llm_client

# Ollama
client = create_llm_client("ollama", model="llama3.1:8b", host="http://localhost:11434")

# OpenAI
client = create_llm_client("openai", model="gpt-4o-mini")
```

### 2. NER Extraction

**File**: `pipeline/ner_extractors.py`

- Created `NERExtractorInterface` abstract base class
- Implemented `BioBERTNERExtractor` using HuggingFace transformers
- Implemented `SciSpaCyNERExtractor` using scispaCy models
- Implemented `OllamaNERExtractor` using LLM prompting
- Factory function `create_ner_extractor()` for easy instantiation

**Updated**: `pipeline/mentions.py`
- `MedLitEntityExtractor` now supports multiple NER backends
- Falls back to pre-extracted entities if available
- Extracts from document text if NER extractor is configured

**Usage**:
```python
# BioBERT
extractor = MedLitEntityExtractor(ner_provider="biobert")

# scispaCy
extractor = MedLitEntityExtractor(ner_provider="scispacy", ner_model="en_ner_bc5cdr_md")

# Ollama
extractor = MedLitEntityExtractor(ner_provider="ollama", ner_model="llama3.1:8b")
```

### 3. Relationship Extraction

**File**: `pipeline/relationships.py`

- Enhanced `MedLitRelationshipExtractor` with:
  - Pattern-based extraction (ported from `claims_pipeline.py`)
  - LLM-based extraction (using LLM client abstraction)
  - Support for pre-extracted relationships
- Pattern matching for common medical predicates:
  - TREATS, CAUSES, PREVENTS, INHIBITS
  - ASSOCIATED_WITH, INTERACTS_WITH
  - DIAGNOSED_BY, INDICATES
- LLM extraction with structured JSON output

**Usage**:
```python
# Pattern-based only
extractor = MedLitRelationshipExtractor(use_patterns=True, use_llm=False)

# LLM-based
llm_client = create_llm_client("ollama", model="llama3.1:8b")
extractor = MedLitRelationshipExtractor(use_patterns=False, use_llm=True, llm_client=llm_client)

# Both
extractor = MedLitRelationshipExtractor(use_patterns=True, use_llm=True, llm_client=llm_client)
```

### 4. Embedding Generation

**File**: `pipeline/embedding_providers.py`

- Implemented `OllamaEmbeddingGenerator` (ports `ollama_embedding_generator.py`)
- Implemented `SentenceTransformerEmbeddingGenerator` (ports `embedding_generators.py`)
- Implemented `HashEmbeddingGenerator` (fallback/placeholder)
- All implement kgraph's `EmbeddingGeneratorInterface`
- Factory function `create_embedding_generator()` for easy instantiation

**Updated**: `pipeline/embeddings.py`
- `SimpleMedLitEmbeddingGenerator` now uses `HashEmbeddingGenerator`
- Re-exports all embedding generators for convenience

**Usage**:
```python
from medlit_kgraph.pipeline.embeddings import create_embedding_generator

# Ollama
embedder = create_embedding_generator("ollama", model_name="nomic-embed-text")

# Sentence Transformers
embedder = create_embedding_generator("sentence-transformers", model_name="all-MiniLM-L6-v2")

# Hash (fallback)
embedder = create_embedding_generator("hash", dimension=32)
```

### 5. Ingestion Script Updates

**File**: `scripts/ingest.py`

- Added command-line arguments for all extractors:
  - `--ner-provider`: Choose NER backend
  - `--ner-model`, `--ner-host`: NER configuration
  - `--embedding-provider`: Choose embedding backend
  - `--embedding-model`, `--embedding-host`: Embedding configuration
  - `--use-pattern-extraction`: Enable/disable pattern extraction
  - `--use-llm-extraction`: Enable LLM extraction
  - `--llm-provider`, `--llm-model`, `--llm-host`: LLM configuration

**Example Usage**:
```bash
# Use BioBERT for NER, Ollama for embeddings, pattern extraction
uv run python -m medlit_kgraph.scripts.ingest \
    --input-dir output/json_papers \
    --output-dir medlit_bundle \
    --ner-provider biobert \
    --embedding-provider ollama \
    --embedding-model nomic-embed-text \
    --use-pattern-extraction

# Use Ollama for everything
uv run python -m medlit_kgraph.scripts.ingest \
    --input-dir output/json_papers \
    --output-dir medlit_bundle \
    --ner-provider ollama \
    --ner-model llama3.1:8b \
    --embedding-provider ollama \
    --embedding-model nomic-embed-text \
    --use-llm-extraction \
    --llm-model llama3.1:8b
```

## Architecture Benefits

1. **Abstraction Layers**: LLM and embedding providers are abstracted, making it easy to swap implementations
2. **Flexible Configuration**: All extractors can be configured via command-line or programmatically
3. **Backward Compatible**: Still works with pre-extracted entities/relationships from med-lit-schema
4. **kgraph Integration**: All components implement kgraph's interfaces, ensuring compatibility

## Remaining Work

1. **Testing**: Add comprehensive tests for all extractors
2. **Error Handling**: Improve error handling and retry logic for API-based extractors
3. **Performance**: Optimize batch processing for large document sets
4. **Documentation**: Add more detailed usage examples and configuration guides

## References

- Original implementations in `med-lit-schema/ingest/`:
  - `ner_pipeline.py` → `ner_extractors.py`, `mentions.py`
  - `claims_pipeline.py` → `relationships.py`
  - `embeddings_pipeline.py`, `ollama_embedding_generator.py` → `embedding_providers.py`
- kgraph interfaces:
  - `kgraph.pipeline.interfaces.EntityExtractorInterface`
  - `kgraph.pipeline.interfaces.RelationshipExtractorInterface`
  - `kgraph.pipeline.embedding.EmbeddingGeneratorInterface`
