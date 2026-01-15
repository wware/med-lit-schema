#!/usr/bin/env python3
"""
Stage 1: Entity Extraction Ingest

Extracts biomedical entities from PMC XML files using BioBERT NER model.
Uses storage interfaces for flexible backend support.

Usage:
    python ner_pipeline.py --storage sqlite --output-dir output
    python ner_pipeline.py --storage postgres --database-url postgresql://...
"""

import argparse
from pathlib import Path
from datetime import datetime
import json
import socket
import platform
import subprocess
import uuid
from itertools import combinations

from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
from lxml import etree
import ollama

# spaCy import is optional - scispacy has dependency issues on Python 3.13+
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

# Import new schema
# Try relative imports first (when run as module), fall back to absolute
try:
    from ..base import EntityType, EntityReference, ModelInfo, ExtractionEdge, Provenance
    from ..entity import (
        Disease,
        ExtractionProvenance,
        ExtractionPipelineInfo,
        PromptInfo,
        ExecutionInfo,
        EntityResolutionInfo,
    )
    from ..storage.interfaces import PipelineStorageInterface
    from ..storage.backends.sqlite import SQLitePipelineStorage
    from ..storage.backends.postgres import PostgresPipelineStorage
except ImportError:
    # Absolute imports for standalone execution
    from med_lit_schema.base import EntityType, EntityReference, ModelInfo, ExtractionEdge, Provenance
    from med_lit_schema.entity import (
        Disease,
        ExtractionProvenance,
        ExtractionPipelineInfo,
        PromptInfo,
        ExecutionInfo,
        EntityResolutionInfo,
    )
    from med_lit_schema.storage.interfaces import PipelineStorageInterface
    from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage
    from med_lit_schema.storage.backends.postgres import PostgresPipelineStorage

from sqlalchemy import create_engine
from sqlmodel import Session


# ============================================================================
# Ollama-based NER Extractor
# ============================================================================

OLLAMA_NER_PROMPT = """Extract all disease and medical condition entities from the following text.
Return ONLY a JSON array of objects with "entity" (the disease name) and "confidence" (0.0-1.0) fields.
Do not include any explanation, just the JSON array.

Example output:
[{{"entity": "diabetes", "confidence": 0.95}}, {{"entity": "hypertension", "confidence": 0.90}}]

If no diseases are found, return an empty array: []

Text to analyze:
{text}

JSON output:"""


class OllamaNerExtractor:
    """
    Ollama-based Named Entity Recognition extractor.

    Uses an LLM to extract disease entities from text via prompting.
    This provides GPU acceleration when connected to a remote Ollama server.
    """

    def __init__(self, host: str = "http://localhost:11434", model: str = "llama3.1:8b", timeout: float = 300.0):
        """
        Initialize the Ollama NER extractor.

        Args:

            host: Ollama server URL
            model: LLM model to use for extraction
            timeout: Request timeout in seconds
        """
        self.host = host
        self.model = model
        self._client = ollama.Client(host=host, timeout=timeout)

    def extract_entities(self, text: str) -> list[dict]:
        """
        Extract disease entities from text using LLM.

        Args:

            text: Text to extract entities from

        Returns:

            List of dicts with 'word', 'entity_group', and 'score' keys
            (matching HuggingFace NER pipeline output format)
        """
        if not text or len(text.strip()) < 10:
            return []

        # Use larger text chunks (8000 chars) for better efficiency
        # The LLM can handle this easily, and it reduces API calls significantly
        prompt = OLLAMA_NER_PROMPT.format(text=text[:8000])

        try:
            response = self._client.generate(
                model=self.model,
                prompt=prompt,
                options={"temperature": 0.1},  # Low temperature for consistent extraction
            )

            # Parse JSON response
            response_text = response.get("response", "").strip()

            # Try to extract JSON from the response
            # Sometimes LLMs add extra text around the JSON
            json_start = response_text.find("[")
            json_end = response_text.rfind("]") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                entities = json.loads(json_str)

                # Convert to HuggingFace NER pipeline format
                results = []
                for ent in entities:
                    if isinstance(ent, dict) and "entity" in ent:
                        results.append({"word": ent["entity"], "entity_group": "Disease", "score": float(ent.get("confidence", 0.85))})
                return results

        except json.JSONDecodeError:
            # If JSON parsing fails, return empty list
            pass
        except Exception as e:
            # Check if it's a timeout specifically
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                print(f"    Warning: Ollama NER extraction timed out (chunk may be too large or server overloaded): {e}")
            else:
                print(f"    Warning: Ollama NER extraction failed: {e}")

        return []


# ============================================================================
# spaCy-based NER Extractor (scispaCy models)
# ============================================================================


class SpacyNerExtractor:
    """
    spaCy-based Named Entity Recognition extractor using scispaCy models.

    Uses en_ner_bc5cdr_md model trained on BioCreative V CDR corpus for
    DISEASE and CHEMICAL entity recognition. Much faster than transformer
    or LLM-based approaches on CPU.

    Note: Requires scispacy which has dependency issues on Python 3.13+.
    If unavailable, use --ner-backend=biobert-fast as an alternative.
    """

    def __init__(self, model_name: str = "en_ner_bc5cdr_md"):
        """
        Initialize the spaCy NER extractor.

        Args:

            model_name: scispaCy model to load (default: en_ner_bc5cdr_md)

        Raises:

            ImportError: If spaCy/scispacy is not available
        """
        if not SPACY_AVAILABLE:
            raise ImportError(
                "spaCy is not available. Install with: uv add scispacy\n"
                "Note: scispacy has dependency issues on Python 3.13+. "
                "Consider using --ner-backend=biobert-fast instead."
            )
        self.model_name = model_name
        self.nlp = spacy.load(model_name)

    def extract_entities(self, text: str) -> list[dict]:
        """
        Extract disease entities from text using spaCy NER.

        Args:

            text: Text to extract entities from

        Returns:

            List of dicts with 'word', 'entity_group', and 'score' keys
            (matching HuggingFace NER pipeline output format)
        """
        if not text or len(text.strip()) < 10:
            return []

        doc = self.nlp(text)
        results = []

        for ent in doc.ents:
            # BC5CDR model returns DISEASE and CHEMICAL labels
            # Map to our expected format, only keep DISEASE for now
            if ent.label_ == "DISEASE":
                results.append({
                    "word": ent.text,
                    "entity_group": "Disease",
                    "score": 0.90,  # spaCy doesn't provide confidence scores by default
                })

        return results


# ============================================================================
# Fast HuggingFace NER Extractor (lighter alternative to BioBERT)
# ============================================================================


class FastBioBertExtractor:
    """
    Faster HuggingFace-based biomedical NER using a lighter model.

    Uses d4data/biomedical-ner-all which is multi-entity (diseases, chemicals,
    genes, etc.) and faster than the full BioBERT models while still being
    specialized for biomedical text.
    """

    def __init__(self, model_name: str = "d4data/biomedical-ner-all"):
        """
        Initialize the fast BioBERT NER extractor.

        Args:

            model_name: HuggingFace model to use
        """
        self.model_name = model_name
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForTokenClassification.from_pretrained(model_name)
        self._pipeline = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")

    def extract_entities(self, text: str) -> list[dict]:
        """
        Extract disease entities from text.

        Args:

            text: Text to extract entities from

        Returns:

            List of dicts with 'word', 'entity_group', and 'score' keys
        """
        if not text or len(text.strip()) < 10:
            return []

        results = []
        # Process in chunks to avoid tokenizer limits
        chunk_size = 512 * 4  # ~4x token limit in chars as rough estimate

        for i in range(0, len(text), chunk_size):
            chunk = text[i:i + chunk_size]
            try:
                ner_results = self._pipeline(chunk)
                for ent in ner_results:
                    label = ent.get("entity_group", "")
                    # d4data model uses labels like "Disease_disorder"
                    if "disease" in label.lower() or "disorder" in label.lower():
                        results.append({
                            "word": ent["word"],
                            "entity_group": "Disease",
                            "score": float(ent.get("score", 0.85)),
                        })
            except Exception as e:
                print(f"    Warning: NER extraction failed for chunk: {e}")

        return results


# Global variable for multiprocessing worker - holds the NER extractor
_worker_ner_extractor = None


def _init_worker(backend: str, model_name: str, ollama_host: str = None):
    """
    Initialize NER extractor in worker process.

    Called once per worker to load the model, avoiding repeated model loading.
    """
    global _worker_ner_extractor

    if backend == "spacy":
        _worker_ner_extractor = SpacyNerExtractor(model_name)
    elif backend == "ollama":
        _worker_ner_extractor = OllamaNerExtractor(host=ollama_host, model=model_name)
    elif backend == "biobert-fast":
        _worker_ner_extractor = FastBioBertExtractor(model_name)
    else:
        # BioBERT / HuggingFace (original slow model)
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForTokenClassification.from_pretrained(model_name)
        _worker_ner_extractor = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")


def get_git_info():
    """Get git information for provenance tracking."""
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
        commit_short = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
        dirty = subprocess.call(["git", "diff", "--quiet"]) != 0
        return commit, commit_short, branch, dirty
    except Exception:
        return "unknown", "unknown", "unknown", False


def get_or_create_entity(
    storage: PipelineStorageInterface,
    name: str,
    entity_type: str = "Disease",
    source: str = None,
    confidence: float = None,
) -> tuple[str, bool]:
    """
    Get existing entity or create new canonical Disease entity.

    Uses entity collection interface for storage. Entity resolution uses
    simple name matching - synonyms are stored in the entity's synonyms field.

    Args:
        storage: Pipeline storage interface
        name: Entity name as extracted from text
        entity_type: Entity type (currently only Disease supported by NER model)
        source: PMC ID where entity was found
        confidence: NER confidence score

    Returns:
        tuple: (canonical_entity_id, was_created) where was_created is True if new entity
    """
    # Try to find existing entity by name
    # First check if we can find by exact name match
    # Note: This is simplified - full implementation would use embedding similarity

    canonical_entity_id = f"DISEASE:{name.lower().replace(' ', '_')}"

    # Try to get existing entity
    existing = storage.entities.get_by_id(canonical_entity_id)
    if existing:
        # Entity exists - add this name as a synonym if not already present
        if name not in existing.synonyms and name != existing.name:
            existing.synonyms.append(name)
            storage.entities.add_disease(existing)
        return canonical_entity_id, False

    # Create new Disease entity
    disease = Disease(entity_id=canonical_entity_id, entity_type=EntityType.DISEASE, name=name, synonyms=[], abbreviations=[], source="extracted")

    storage.entities.add_disease(disease)
    return canonical_entity_id, True


def extract_paragraphs_from_xml(xml_path: Path) -> tuple[str, list[str], bool]:
    """
    Extract paragraphs from a PMC XML file.

    Args:

        xml_path: Path to PMC XML file

    Returns:

        tuple: (pmc_id, paragraphs, abstract_only) where abstract_only is True
               if no body text was found
    """
    pmc_id = xml_path.stem
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    abstract_paragraphs = [p.text.strip() for p in root.findall(".//abstract//p") if p.text and p.text.strip()]

    body_paragraphs = []
    for sec in root.findall(".//body//sec"):
        sec_type = (sec.get("sec-type") or "").lower()
        if sec_type in {"ref", "references", "ack", "acknowledgements"}:
            continue

        for p in sec.findall(".//p"):
            if p.text and p.text.strip():
                body_paragraphs.append(p.text.strip())

    paragraphs = abstract_paragraphs + body_paragraphs
    abstract_only = bool(abstract_paragraphs and not body_paragraphs)

    return pmc_id, paragraphs, abstract_only


def chunk_paragraphs(paragraphs: list[str], chunk_size: int = 8000) -> list[str]:
    """
    Batch paragraphs into larger chunks to reduce NER calls.

    Args:

        paragraphs: List of paragraph texts
        chunk_size: Target chunk size in characters

    Returns:

        List of text chunks
    """
    chunks = []
    current_chunk = []
    current_length = 0

    for para in paragraphs:
        para_len = len(para)
        if current_length + para_len > chunk_size and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [para]
            current_length = para_len
        else:
            current_chunk.append(para)
            current_length += para_len + 2

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


# Stopwords for entity filtering
STOPWORDS = frozenset({"the", "and", "or", "but", "with", "from", "that", "this", "these", "those", "their", "there"})


def extract_entities_from_paper(
    xml_path: Path,
    ner_extractor,
) -> tuple[str, list[dict], bool]:
    """
    Extract raw entity mentions from a PMC XML file.

    This is a pure function suitable for multiprocessing - no storage access.

    Args:

        xml_path: Path to PMC XML file
        ner_extractor: NER extractor with extract_entities() method, or HuggingFace pipeline

    Returns:

        tuple: (pmc_id, entity_mentions, abstract_only)
               entity_mentions is a list of dicts with 'name', 'confidence' keys
    """
    pmc_id, paragraphs, abstract_only = extract_paragraphs_from_xml(xml_path)

    if not paragraphs:
        return pmc_id, [], abstract_only

    chunks = chunk_paragraphs(paragraphs)
    entity_mentions = []

    for chunk_text in chunks:
        # Handle both extractor classes and HuggingFace pipelines
        if hasattr(ner_extractor, 'extract_entities'):
            ner_results = ner_extractor.extract_entities(chunk_text)
        else:
            ner_results = ner_extractor(chunk_text)

        for ent in ner_results:
            label = ent.get("entity_group", ent.get("entity", "O"))
            if label != "Disease":
                continue

            name = ent["word"].strip()
            confidence = float(ent.get("score", 0.0))

            # Basic hygiene filters
            if len(name) < 3:
                continue
            if name.startswith("##"):
                continue
            if name.lower() in STOPWORDS:
                continue
            if confidence < 0.85:
                continue

            entity_mentions.append({"name": name, "confidence": confidence})

    return pmc_id, entity_mentions, abstract_only


def process_paper_worker(xml_path_str: str) -> tuple[str, list[dict], bool]:
    """
    Worker function for multiprocessing.

    Uses global _worker_ner_extractor initialized by _init_worker().

    Args:

        xml_path_str: String path to XML file (strings required for pickling)

    Returns:

        tuple: (pmc_id, entity_mentions, abstract_only)
    """
    global _worker_ner_extractor
    return extract_entities_from_paper(Path(xml_path_str), _worker_ner_extractor)


def process_paper(
    xml_path: Path,
    storage: PipelineStorageInterface,
    ner_extractor,
    ingest_info: ExtractionPipelineInfo,
    model_info: ModelInfo,
) -> tuple[int, int, list]:
    """
    Process a single PMC XML file and extract entities.

    This version is for single-threaded processing with storage access.

    Args:

        xml_path: Path to PMC XML file
        storage: Pipeline storage interface
        ner_extractor: NER extractor
        ingest_info: Pipeline info for provenance
        model_info: Model info for provenance

    Returns:

        tuple: (entities_found, entities_created, extraction_edges)
    """
    pmc_id, entity_mentions, abstract_only = extract_entities_from_paper(xml_path, ner_extractor)

    if abstract_only:
        print(f"⚠️  WARNING: {pmc_id} contains abstract only (no body text found)")

    if not entity_mentions:
        return 0, 0, []

    return process_entity_mentions(pmc_id, entity_mentions, storage, ingest_info, model_info)


def process_entity_mentions(
    pmc_id: str,
    entity_mentions: list[dict],
    storage: PipelineStorageInterface,
    ingest_info: ExtractionPipelineInfo,
    model_info: ModelInfo,
) -> tuple[int, int, list]:
    """
    Process extracted entity mentions: resolve to canonical entities and build edges.

    Args:

        pmc_id: PMC ID of the paper
        entity_mentions: List of dicts with 'name', 'confidence' keys
        storage: Pipeline storage interface
        ingest_info: Pipeline info for provenance
        model_info: Model info for provenance

    Returns:

        tuple: (entities_found, entities_created, extraction_edges)
    """
    entities_found = 0
    entities_created = 0
    extraction_edges = []

    # Resolve entities and track for edge building
    resolved_entities: list[tuple[EntityReference, float]] = []

    for mention in entity_mentions:
        name = mention["name"]
        confidence = mention["confidence"]

        canonical_entity_id, was_created = get_or_create_entity(
            storage=storage,
            name=name,
            entity_type="Disease",
            source=pmc_id,
            confidence=confidence,
        )

        if was_created:
            entities_created += 1
        entities_found += 1

        entity_ref = EntityReference(
            id=canonical_entity_id,
            name=name,
            type=EntityType.DISEASE,
        )
        resolved_entities.append((entity_ref, confidence))

    # Build co-occurrence edges
    MIN_EDGE_CONFIDENCE = 0.9
    for (subj_ref, conf_i), (obj_ref, conf_j) in combinations(resolved_entities, 2):
        if subj_ref.id == obj_ref.id:
            continue

        edge_confidence = min(conf_i, conf_j)
        if edge_confidence < MIN_EDGE_CONFIDENCE:
            continue

        provenance = Provenance(
            source_type="paper",
            source_id=pmc_id,
            source_version=None,
            notes=json.dumps({
                "extraction_pipeline": ingest_info.name,
                "git_commit": ingest_info.git_commit_short,
                "model": model_info.name,
                "scope": "paper",
            }),
        )

        edge = ExtractionEdge(
            id=uuid.uuid4(),
            subject=subj_ref,
            object=obj_ref,
            provenance=provenance,
            extractor=model_info,
            confidence=edge_confidence,
        )
        extraction_edges.append(edge)

    return entities_found, entities_created, extraction_edges


def main():
    """Main ingest execution."""
    parser = argparse.ArgumentParser(description="Stage 1: Entity Extraction Pipeline")
    parser.add_argument("--xml-dir", type=str, default="pmc_xmls", help="Directory containing PMC XML files")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory")
    parser.add_argument("--storage", type=str, choices=["sqlite", "postgres"], default="sqlite", help="Storage backend to use")
    parser.add_argument("--database-url", type=str, default=None, help="Database URL for PostgreSQL (required if --storage=postgres)")
    parser.add_argument("--ner-backend", type=str, choices=["spacy", "ollama", "biobert", "biobert-fast"], default="biobert-fast", help="NER backend: spacy (fastest, needs scispacy), biobert-fast (good CPU speed, default), ollama (LLM-based), biobert (original, slow)")
    parser.add_argument("--spacy-model", type=str, default="en_ner_bc5cdr_md", help="spaCy model for NER (default: en_ner_bc5cdr_md)")
    parser.add_argument("--ollama-host", type=str, default="http://localhost:11434", help="Ollama host URL (default: http://localhost:11434)")
    parser.add_argument("--ollama-model", type=str, default="llama3.1:8b", help="Ollama model to use for NER (default: llama3.1:8b)")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker processes for parallel processing (default: 4, use 1 for single-threaded)")

    args = parser.parse_args()

    xml_dir = Path(args.xml_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Get git info for provenance
    git_commit, git_commit_short, git_branch, git_dirty = get_git_info()

    # Pipeline info for provenance
    ingest_info = ExtractionPipelineInfo(
        name="pmc_ner_ingest",
        version="1.0.0",
        git_commit=git_commit,
        git_commit_short=git_commit_short,
        git_branch=git_branch,
        git_dirty=git_dirty,
        repo_url="https://github.com/wware/med-lit-graph",
    )

    # Model info - depends on NER backend
    if args.ner_backend == "spacy":
        model_name = args.spacy_model
        model_info = ModelInfo(name=model_name, provider="scispacy", temperature=None, version=None)
        prompt_template = "ner_scispacy_bc5cdr"
    elif args.ner_backend == "ollama":
        model_name = args.ollama_model
        model_info = ModelInfo(name=model_name, provider="ollama", temperature=0.1, version=None)
        prompt_template = "ollama_ner_disease"
    elif args.ner_backend == "biobert-fast":
        model_name = "d4data/biomedical-ner-all"
        model_info = ModelInfo(name=model_name, provider="huggingface", temperature=None, version=None)
        prompt_template = "ner_biobert_fast"
    else:  # biobert (original)
        model_name = "ugaray96/biobert_ncbi_disease_ner"
        model_info = ModelInfo(name=model_name, provider="huggingface", temperature=None, version=None)
        prompt_template = "ner_biobert_ncbi_disease"

    # Prompt info
    prompt_info = PromptInfo(version="v1", template=prompt_template, checksum=None)

    # Execution info
    execution_start = datetime.now()
    execution_info = ExecutionInfo(timestamp=execution_start.isoformat(), hostname=socket.gethostname(), python_version=platform.python_version(), duration_seconds=None)

    # Setup NER extractor based on backend
    ner_extractor = None  # Will be None if using multiprocessing
    if args.workers == 1:
        # Single-threaded: load model in main process
        if args.ner_backend == "spacy":
            print(f"Loading spaCy model: {model_name}")
            ner_extractor = SpacyNerExtractor(model_name)
        elif args.ner_backend == "ollama":
            print(f"Using Ollama at {args.ollama_host} for NER")
            print(f"Model: {model_name}")
            ner_extractor = OllamaNerExtractor(host=args.ollama_host, model=model_name)
        elif args.ner_backend == "biobert-fast":
            print(f"Loading fast BioBERT model: {model_name}")
            ner_extractor = FastBioBertExtractor(model_name)
        else:  # biobert (original)
            print(f"Loading BioBERT model: {model_name}")
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForTokenClassification.from_pretrained(model_name)
            ner_extractor = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")
    else:
        print(f"Using {args.workers} worker processes with {args.ner_backend} backend")
        print(f"Model: {model_name}")

    # Process papers
    worker_config = {
        "backend": args.ner_backend,
        "model_name": model_name,
        "ollama_host": args.ollama_host if args.ner_backend == "ollama" else None,
        "num_workers": args.workers,
    }

    if args.storage == "sqlite":
        db_path = output_dir / "ingest.db"
        with SQLitePipelineStorage(db_path) as storage:
            total_entities_found, total_entities_created, all_extraction_edges, processed_count = process_papers(
                xml_dir, storage, ner_extractor, ingest_info, model_info, worker_config
            )
    elif args.storage == "postgres":
        if not args.database_url:
            print("Error: --database-url required for PostgreSQL storage")
            return 1
        engine = create_engine(args.database_url)
        session = Session(engine)
        with PostgresPipelineStorage(session) as storage:
            total_entities_found, total_entities_created, all_extraction_edges, processed_count = process_papers(
                xml_dir, storage, ner_extractor, ingest_info, model_info, worker_config
            )
    else:
        print(f"Error: Unknown storage backend: {args.storage}")
        return 1

    # Finalize provenance
    execution_end = datetime.now()
    execution_duration = (execution_end - execution_start).total_seconds()
    execution_info.duration_seconds = execution_duration

    entity_resolution_info = EntityResolutionInfo(
        canonical_entities_matched=total_entities_found - total_entities_created, new_entities_created=total_entities_created, similarity_threshold=0.0, embedding_model="none"
    )

    extraction_provenance = ExtractionProvenance(extraction_pipeline=ingest_info, models={"ner": model_info}, prompt=prompt_info, execution=execution_info, entity_resolution=entity_resolution_info)

    # Write ExtractionEdge objects to JSONL
    edges_path = output_dir / "extraction_edges.jsonl"
    with open(edges_path, "w") as f:
        for edge in all_extraction_edges:
            edge_dict = edge.model_dump()
            edge_dict["id"] = str(edge_dict["id"])
            f.write(json.dumps(edge_dict) + "\n")

    # Write extraction provenance
    provenance_path = output_dir / "extraction_provenance.json"
    with open(provenance_path, "w") as f:
        f.write(extraction_provenance.model_dump_json(indent=2))

    # Print summary
    print(f"\n{'=' * 60}")
    print("Extraction Complete")
    print(f"{'=' * 60}")
    print(f"Processed: {processed_count} XML files")
    print(f"Entities found: {total_entities_found}")
    print(f"  - New canonical entities: {total_entities_created}")
    print(f"  - Matched to existing: {total_entities_found - total_entities_created}")
    print(f"ExtractionEdges: {len(all_extraction_edges)}")
    print(f"Duration: {execution_duration:.2f} seconds")
    print(f"\nStorage: {args.storage}")
    print("\nOutputs:")
    print(f"  - {edges_path}")
    print(f"  - {provenance_path}")
    print(f"{'=' * 60}\n")
    return 0


def process_papers(xml_dir, storage, ner_extractor, ingest_info, model_info, worker_config):
    """
    Process all XML files and extract entities.

    Supports both single-threaded and multiprocessing modes.

    Args:

        xml_dir: Directory containing PMC XML files
        storage: Pipeline storage interface
        ner_extractor: NER extractor (None if using multiprocessing)
        ingest_info: Pipeline info for provenance
        model_info: Model info for provenance
        worker_config: Dict with 'backend', 'model_name', 'ollama_host', 'num_workers'

    Returns:

        tuple: (total_entities_found, total_entities_created, all_extraction_edges, processed_count)
    """
    print(f"\nProcessing XML files from {xml_dir}...")
    xml_files = sorted(xml_dir.glob("PMC*.xml"))
    print(f"Found {len(xml_files)} XML files\n")

    total_entities_found = 0
    total_entities_created = 0
    all_extraction_edges = []
    processed_count = 0

    num_workers = worker_config["num_workers"]

    if num_workers == 1:
        # Single-threaded mode
        for xml_file in xml_files:
            entities_found, entities_created, edges = process_paper(xml_file, storage, ner_extractor, ingest_info, model_info)
            total_entities_found += entities_found
            total_entities_created += entities_created
            all_extraction_edges.extend(edges)
            processed_count += 1

            if processed_count % 10 == 0:
                print(f"  Processed {processed_count}/{len(xml_files)} files...")
    else:
        # Multiprocessing mode
        # Workers extract entities, main process handles storage
        xml_paths = [str(f) for f in xml_files]

        print(f"Starting extraction with {num_workers} workers...")

        with ProcessPoolExecutor(
            max_workers=num_workers,
            initializer=_init_worker,
            initargs=(worker_config["backend"], worker_config["model_name"], worker_config["ollama_host"]),
        ) as executor:
            # Submit all tasks
            future_to_path = {executor.submit(process_paper_worker, path): path for path in xml_paths}

            # Process results as they complete
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    pmc_id, entity_mentions, abstract_only = future.result()

                    if abstract_only:
                        print(f"⚠️  WARNING: {pmc_id} contains abstract only (no body text found)")

                    if entity_mentions:
                        entities_found, entities_created, edges = process_entity_mentions(
                            pmc_id, entity_mentions, storage, ingest_info, model_info
                        )
                        total_entities_found += entities_found
                        total_entities_created += entities_created
                        all_extraction_edges.extend(edges)

                    processed_count += 1

                    if processed_count % 10 == 0:
                        print(f"  Processed {processed_count}/{len(xml_files)} files...")

                except Exception as e:
                    print(f"  Error processing {path}: {e}")
                    processed_count += 1

        print(f"  Extraction complete. Processing {processed_count} results...")

    return total_entities_found, total_entities_created, all_extraction_edges, processed_count


if __name__ == "__main__":
    exit(main())
