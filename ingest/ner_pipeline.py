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
    Process a single PMC XML file and extract entities.

    Args:
        xml_path: Path to PMC XML file
        storage: Pipeline storage interface
        ner_pipeline: HuggingFace NER pipeline
        ingest_info: Ingest metadata
        model_info: Model metadata

    Returns:
        tuple: (entities_found, entities_created, extraction_edges)
    """
    pmc_id = xml_path.stem
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    # Extract text - prefer abstract, fall back to body
    text_chunks = [p.text for p in root.findall(".//abstract//p") if p.text]
    if not text_chunks:
        text_chunks = [p.text for p in root.findall(".//body//p") if p.text]
    if not text_chunks:
        return 0, 0, []

    full_text = " ".join(text_chunks)

    # Run NER
    entities = ner_pipeline(full_text)
    entity_refs_in_text = []
    entities_created = 0
    entities_found = 0

    STOPWORDS = {"acquired", "human", "chronic", "enter", "lymph", "the", "and", "or", "but", "with", "from", "that", "this", "these", "those", "their", "there"}

    for ent in entities:
        # Filter by entity label
        label = ent.get("entity_group", ent.get("entity", "O"))
        if label != "Disease":
            continue

        name = ent["word"].strip()

        # Skip obvious garbage
        if len(name) < 3:
            continue
        if name in ["(", ")", ",", ".", "-"]:
            continue
        if name.startswith("##"):
            continue
        if name.lower() in STOPWORDS:
            continue

        confidence = ent.get("score", None)
        if confidence and confidence < 0.85:
            continue

        # Get or create canonical entity
        canonical_entity_id, was_created = get_or_create_entity(storage=storage, name=name, entity_type=label, source=pmc_id, confidence=confidence)

        if was_created:
            entities_created += 1
        entities_found += 1

        # Create EntityReference for this mention
        entity_ref = EntityReference(id=canonical_entity_id, name=name, type=EntityType.DISEASE)
        entity_refs_in_text.append(entity_ref)

    # Build ExtractionEdge objects for co-occurrences
    extraction_edges = []
    for i in range(len(entity_refs_in_text)):
        for j in range(i + 1, len(entity_refs_in_text)):
            subject_ref = entity_refs_in_text[i]
            object_ref = entity_refs_in_text[j]

            # Create provenance for this edge
            edge_provenance = Provenance(
                source_type="paper",
                source_id=pmc_id,
                source_version=None,
                notes=json.dumps({"extraction_pipeline": pipeline_info.name, "git_commit": pipeline_info.git_commit_short, "model": model_info.name}),
            )

            # Create ExtractionEdge with full provenance
            edge = ExtractionEdge(
                id=uuid.uuid4(),
                subject=subject_ref,
                object=object_ref,
                provenance=edge_provenance,
                extractor=model_info,
                confidence=min(float(entities[i].get("score", 0.5)), float(entities[j].get("score", 0.5))),
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

    args = parser.parse_args()

    xml_dir = Path(args.xml_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Initialize storage based on choice
    if args.storage == "sqlite":
        db_path = output_dir / "ingest.db"
        storage: PipelineStorageInterface = SQLitePipelineStorage(db_path)
    elif args.storage == "postgres":
        if not args.database_url:
            print("Error: --database-url required for PostgreSQL storage")
            return 1
        storage = PostgresPipelineStorage(args.database_url)
    else:
        print(f"Error: Unknown storage backend: {args.storage}")
        return 1

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

    # Model info
    model_name = "ugaray96/biobert_ncbi_disease_ner"
    model_info = ModelInfo(name=model_name, provider="huggingface", temperature=None, version=None)

    # Prompt info
    prompt_info = PromptInfo(version="v1", template="ner_biobert_ncbi_disease", checksum=None)

    # Execution info
    execution_start = datetime.now()
    execution_info = ExecutionInfo(timestamp=execution_start.isoformat(), hostname=socket.gethostname(), python_version=platform.python_version(), duration_seconds=None)

    # Setup NER ingest
    print(f"Loading NER model: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForTokenClassification.from_pretrained(model_name)
    ner_pipeline = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")

    # Process papers
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
    print(f"Entity count: {storage.entities.entity_count}")
    print("\nOutputs:")
    print(f"  - Storage: {storage}")
    print(f"  - {edges_path}")
    print(f"  - {provenance_path}")
    print(f"{'=' * 60}\n")

    # Clean up
    storage.close()
    return 0


if __name__ == "__main__":
    exit(main())
