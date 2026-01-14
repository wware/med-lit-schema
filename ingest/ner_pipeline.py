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

from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
from lxml import etree
import ollama

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
[{"entity": "diabetes", "confidence": 0.95}, {"entity": "hypertension", "confidence": 0.90}]

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

    def __init__(self, host: str = "http://localhost:11434", model: str = "llama3.1:8b", timeout: float = 120.0):
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

        prompt = OLLAMA_NER_PROMPT.format(text=text[:2000])  # Limit text length

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
            print(f"    Warning: Ollama NER extraction failed: {e}")

        return []


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


def process_paper(
    xml_path: Path,
    storage: PipelineStorageInterface,
    ner_pipeline,
    ingest_info: ExtractionPipelineInfo,
    model_info: ModelInfo,
) -> tuple[int, int, list]:
    """
    Process a single PMC XML file and extract entities at paragraph level.

    - Runs NER per paragraph (avoids truncation)
    - Builds co-occurrence edges within paragraphs only
    - Emits warning if only abstracts are ingested
    """
    pmc_id = xml_path.stem
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    # -----------------------------
    # Paragraph extraction
    # -----------------------------

    abstract_paragraphs = [p.text.strip() for p in root.findall(".//abstract//p") if p.text and p.text.strip()]

    body_paragraphs = []
    for sec in root.findall(".//body//sec"):
        sec_type = (sec.get("sec-type") or "").lower()
        if sec_type in {"ref", "references", "ack", "acknowledgements"}:
            continue

        for p in sec.findall(".//p"):
            if p.text and p.text.strip():
                body_paragraphs.append(p.text.strip())

    if not abstract_paragraphs and not body_paragraphs:
        return 0, 0, []

    if abstract_paragraphs and not body_paragraphs:
        print(f"⚠️  WARNING: {pmc_id} contains abstract only (no body text found)")

    paragraphs = abstract_paragraphs + body_paragraphs

    # -----------------------------
    # Entity extraction
    # -----------------------------

    entities_found = 0
    entities_created = 0
    extraction_edges = []

    STOPWORDS = {"the", "and", "or", "but", "with", "from", "that", "this", "these", "those", "their", "there"}

    for paragraph_text in paragraphs:
        ner_results = ner_pipeline(paragraph_text)

        # Track entities found in this paragraph only
        paragraph_entities: list[tuple[EntityReference, float]] = []

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

            canonical_entity_id, was_created = get_or_create_entity(
                storage=storage,
                name=name,
                entity_type=label,
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

            paragraph_entities.append((entity_ref, confidence))

        # -----------------------------
        # Build co-occurrence edges (paragraph-local)
        # -----------------------------

        for i in range(len(paragraph_entities)):
            subj_ref, conf_i = paragraph_entities[i]
            for j in range(i + 1, len(paragraph_entities)):
                obj_ref, conf_j = paragraph_entities[j]

                provenance = Provenance(
                    source_type="paper",
                    source_id=pmc_id,
                    source_version=None,
                    notes=json.dumps(
                        {
                            "extraction_pipeline": ingest_info.name,
                            "git_commit": ingest_info.git_commit_short,
                            "model": model_info.name,
                            "scope": "paragraph",
                        }
                    ),
                )

                edge = ExtractionEdge(
                    id=uuid.uuid4(),
                    subject=subj_ref,
                    object=obj_ref,
                    provenance=provenance,
                    extractor=model_info,
                    confidence=min(conf_i, conf_j),
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
    parser.add_argument("--ollama-host", type=str, default=None, help="Ollama host URL (e.g., http://localhost:11434). If provided, uses Ollama LLM for NER instead of BioBERT.")
    parser.add_argument("--ollama-model", type=str, default="llama3.1:8b", help="Ollama model to use for NER (default: llama3.1:8b)")

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

    # Model info - depends on whether using Ollama or BioBERT
    if args.ollama_host:
        model_name = args.ollama_model
        model_info = ModelInfo(name=model_name, provider="ollama", temperature=0.1, version=None)
        prompt_template = "ollama_ner_disease"
    else:
        model_name = "ugaray96/biobert_ncbi_disease_ner"
        model_info = ModelInfo(name=model_name, provider="huggingface", temperature=None, version=None)
        prompt_template = "ner_biobert_ncbi_disease"

    # Prompt info
    prompt_info = PromptInfo(version="v1", template=prompt_template, checksum=None)

    # Execution info
    execution_start = datetime.now()
    execution_info = ExecutionInfo(timestamp=execution_start.isoformat(), hostname=socket.gethostname(), python_version=platform.python_version(), duration_seconds=None)

    # Setup NER extractor - either Ollama (GPU) or BioBERT (CPU)
    if args.ollama_host:
        print(f"Using Ollama at {args.ollama_host} for GPU-accelerated NER")
        print(f"Model: {model_name}")
        ollama_extractor = OllamaNerExtractor(host=args.ollama_host, model=model_name)

        # Create a callable wrapper that matches HuggingFace pipeline interface
        def ner_pipeline(text):
            return ollama_extractor.extract_entities(text)

    else:
        print(f"Loading NER model: {model_name}")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForTokenClassification.from_pretrained(model_name)
        ner_pipeline = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")

    # Process papers
    if args.storage == "sqlite":
        db_path = output_dir / "ingest.db"
        with SQLitePipelineStorage(db_path) as storage:
            total_entities_found, total_entities_created, all_extraction_edges, processed_count = process_papers(xml_dir, storage, ner_pipeline, ingest_info, model_info)
    elif args.storage == "postgres":
        if not args.database_url:
            print("Error: --database-url required for PostgreSQL storage")
            return 1
        engine = create_engine(args.database_url)
        session = Session(engine)
        with PostgresPipelineStorage(session) as storage:
            total_entities_found, total_entities_created, all_extraction_edges, processed_count = process_papers(xml_dir, storage, ner_pipeline, ingest_info, model_info)
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


def process_papers(xml_dir, storage, ner_pipeline, ingest_info, model_info):
    """Processes all XML files and extracts entities."""
    print(f"\nProcessing XML files from {xml_dir}...")
    xml_files = sorted(xml_dir.glob("PMC*.xml"))
    print(f"Found {len(xml_files)} XML files\n")

    total_entities_found = 0
    total_entities_created = 0
    all_extraction_edges = []
    processed_count = 0

    for xml_file in xml_files:
        entities_found, entities_created, edges = process_paper(xml_file, storage, ner_pipeline, ingest_info, model_info)
        total_entities_found += entities_found
        total_entities_created += entities_created
        all_extraction_edges.extend(edges)
        processed_count += 1

        if processed_count % 10 == 0:
            print(f"  Processed {processed_count}/{len(xml_files)} files...")

    return total_entities_found, total_entities_created, all_extraction_edges, processed_count


if __name__ == "__main__":
    exit(main())
