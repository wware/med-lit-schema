# Setup Guide for medlit_kgraph Extension

## Default Configuration (No Setup Required)

The default configuration works **out of the box** with no external resources:

- **NER**: `none` - Uses pre-extracted entities from Paper JSON files
- **Embeddings**: `hash` - Hash-based embeddings (no external models)
- **Relationship Extraction**: Pattern-based (regex patterns, no LLM)
- **LLM Extraction**: Disabled

You can run the ingestion script immediately:

```bash
uv run python -m medlit_kgraph.scripts.ingest \
    --input-dir output/json_papers \
    --output-dir medlit_bundle
```

## Optional: Setting Up Advanced Extractors

### 1. Ollama Setup (for NER, Embeddings, or LLM Extraction)

If you want to use Ollama for any extraction:

**Install Ollama**:
```bash
# On Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh

# Or download from https://ollama.com/download
```

**Start Ollama server**:
```bash
ollama serve
```

**Pull required models**:
```bash
# For embeddings
ollama pull nomic-embed-text

# For NER/LLM extraction
ollama pull llama3.1:8b
# Or for medical domain:
ollama pull meditron:70b  # If available
```

**Usage**:
```bash
# Use Ollama for embeddings
uv run python -m medlit_kgraph.scripts.ingest \
    --input-dir output/json_papers \
    --output-dir medlit_bundle \
    --embedding-provider ollama \
    --embedding-model nomic-embed-text

# Use Ollama for NER
uv run python -m medlit_kgraph.scripts.ingest \
    --input-dir output/json_papers \
    --output-dir medlit_bundle \
    --ner-provider ollama \
    --ner-model llama3.1:8b

# Use Ollama for relationship extraction
uv run python -m medlit_kgraph.scripts.ingest \
    --input-dir output/json_papers \
    --output-dir medlit_bundle \
    --use-llm-extraction \
    --llm-model llama3.1:8b
```

**Remote Ollama**: If Ollama is running on a different host:
```bash
--ner-host http://your-ollama-host:11434
--embedding-host http://your-ollama-host:11434
--llm-host http://your-ollama-host:11434
```

### 2. BioBERT Setup (for NER)

BioBERT uses HuggingFace transformers (already in dependencies).

**No additional setup needed** - models download automatically on first use.

**Usage**:
```bash
uv run python -m medlit_kgraph.scripts.ingest \
    --input-dir output/json_papers \
    --output-dir medlit_bundle \
    --ner-provider biobert
```

**Note**: First run will download the model (~400MB), which may take a few minutes.

### 3. scispaCy Setup (for NER)

scispaCy requires additional installation due to dependency issues on Python 3.13+.

**Install scispaCy**:
```bash
uv pip install scispacy
```

**Download model**:
```bash
# Download the BC5CDR model (diseases and chemicals)
python -m spacy download en_ner_bc5cdr_md

# Or download other scispaCy models:
# python -m spacy download en_core_sci_sm
# python -m spacy download en_core_sci_md
```

**Usage**:
```bash
uv run python -m medlit_kgraph.scripts.ingest \
    --input-dir output/json_papers \
    --output-dir medlit_bundle \
    --ner-provider scispacy \
    --ner-model en_ner_bc5cdr_md
```

### 4. Sentence Transformers Setup (for Embeddings)

Sentence Transformers is already in dependencies. Models download automatically on first use.

**Usage**:
```bash
uv run python -m medlit_kgraph.scripts.ingest \
    --input-dir output/json_papers \
    --output-dir medlit_bundle \
    --embedding-provider sentence-transformers \
    --embedding-model sentence-transformers/all-MiniLM-L6-v2
```

**Note**: First run will download the model (~80MB for all-MiniLM-L6-v2), which may take a minute.

### 5. OpenAI Setup (for LLM Extraction)

**Set API key**:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

**Usage**:
```bash
uv run python -m medlit_kgraph.scripts.ingest \
    --input-dir output/json_papers \
    --output-dir medlit_bundle \
    --use-llm-extraction \
    --llm-provider openai \
    --llm-model gpt-4o-mini
```

## Quick Reference

| Feature | Default | Setup Required? |
|---------|---------|----------------|
| NER | `none` (pre-extracted) | ❌ No |
| Embeddings | `hash` | ❌ No |
| Relationship Extraction | Pattern-based | ❌ No |
| LLM Extraction | Disabled | ❌ No |
| Ollama | N/A | ✅ Yes (if using) |
| BioBERT | N/A | ❌ Auto-downloads |
| scispaCy | N/A | ✅ Manual install |
| Sentence Transformers | N/A | ❌ Auto-downloads |
| OpenAI | N/A | ✅ API key needed |

## Troubleshooting

### Ollama Connection Errors

If you see errors like "Connection refused" or "Failed to connect to Ollama":
1. Ensure Ollama server is running: `ollama serve`
2. Check the host URL matches your setup
3. Verify models are pulled: `ollama list`

### Model Download Issues

If models fail to download:
1. Check internet connection
2. For HuggingFace models, ensure you have enough disk space
3. For scispaCy, ensure Python version is compatible (may have issues on 3.13+)

### Memory Issues

- BioBERT and large Ollama models require significant RAM
- Consider using smaller models or CPU-only versions
- For BioBERT, you can specify device: `--ner-device -1` (CPU)

## Recommended Setup for Production

For processing many papers with good quality:

1. **NER**: Use BioBERT or Ollama (better than pre-extracted for raw text)
2. **Embeddings**: Use Ollama `nomic-embed-text` or sentence-transformers
3. **Relationships**: Use both pattern-based and LLM extraction

Example:
```bash
uv run python -m medlit_kgraph.scripts.ingest \
    --input-dir output/json_papers \
    --output-dir medlit_bundle \
    --ner-provider biobert \
    --embedding-provider ollama \
    --embedding-model nomic-embed-text \
    --use-pattern-extraction \
    --use-llm-extraction \
    --llm-model llama3.1:8b
```
