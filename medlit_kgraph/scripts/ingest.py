#!/usr/bin/env python3
"""Ingestion script for medical literature knowledge graph.

Processes Paper JSON files or PMC XML files and generates a kgraph bundle.

Usage:
    python -m medlit_kgraph.scripts.ingest --input-dir /path/to/json_papers --output-dir medlit_bundle
    python -m medlit_kgraph.scripts.ingest --input-dir /path/to/pmc_xmls --output-dir medlit_bundle --content-type xml
"""

import argparse
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from kgraph.ingest import IngestionOrchestrator
from kgraph.storage.memory import (
    InMemoryDocumentStorage,
    InMemoryEntityStorage,
    InMemoryRelationshipStorage,
)
from kgraph.export import write_bundle

from ..domain.domain import MedLitDomainSchema
from ..pipeline.parser import JournalArticleParser
from ..pipeline.mentions import MedLitEntityExtractor
from ..pipeline.resolve import MedLitEntityResolver
from ..pipeline.relationships import MedLitRelationshipExtractor
from ..pipeline.embeddings import create_embedding_generator, SimpleMedLitEmbeddingGenerator
from ..pipeline.llm_client import create_llm_client


def build_orchestrator(
    ner_provider: str = "none",
    ner_model: str | None = None,
    ner_host: str | None = None,
    embedding_provider: str = "hash",
    embedding_model: str | None = None,
    embedding_host: str | None = None,
    use_pattern_extraction: bool = True,
    use_llm_extraction: bool = False,
    llm_provider: str = "ollama",
    llm_model: str = "llama3.1:8b",
    llm_host: str = "http://localhost:11434",
) -> IngestionOrchestrator:
    """Build the ingestion orchestrator for medical literature domain.

    Args:
        ner_provider: NER provider ("none", "biobert", "scispacy", "ollama")
        ner_model: NER model name (provider-specific)
        ner_host: Ollama host URL (for Ollama NER)
        embedding_provider: Embedding provider ("hash", "ollama", "sentence-transformers")
        embedding_model: Embedding model name
        embedding_host: Ollama host URL (for Ollama embeddings)
        use_pattern_extraction: Enable pattern-based relationship extraction
        use_llm_extraction: Enable LLM-based relationship extraction
        llm_provider: LLM provider ("ollama", "openai")
        llm_model: LLM model name
        llm_host: LLM host URL (for Ollama)
    """
    domain = MedLitDomainSchema()

    # Build entity extractor
    ner_kwargs = {}
    if ner_provider == "ollama":
        if ner_model:
            ner_kwargs["model"] = ner_model
        if ner_host:
            ner_kwargs["host"] = ner_host
    elif ner_provider == "biobert" and ner_model:
        ner_kwargs["model_name"] = ner_model
    elif ner_provider == "scispacy" and ner_model:
        ner_kwargs["model_name"] = ner_model

    entity_extractor = MedLitEntityExtractor(
        ner_provider=ner_provider,
        **ner_kwargs,
    )

    # Build relationship extractor
    llm_client = None
    if use_llm_extraction:
        llm_kwargs = {"model": llm_model, "host": llm_host}
        if llm_provider == "openai":
            # OpenAI uses api_key from env var
            llm_kwargs.pop("host", None)
        try:
            llm_client = create_llm_client(llm_provider, **llm_kwargs)
        except Exception as e:
            print(f"Warning: Failed to create LLM client: {e}")
            print("  Continuing without LLM extraction...")
            use_llm_extraction = False

    relationship_extractor = MedLitRelationshipExtractor(
        use_patterns=use_pattern_extraction,
        use_llm=use_llm_extraction,
        llm_client=llm_client,
    )

    # Build embedding generator
    embedding_kwargs = {}
    if embedding_provider == "ollama":
        if embedding_model:
            embedding_kwargs["model_name"] = embedding_model
        if embedding_host:
            embedding_kwargs["host"] = embedding_host
    elif embedding_provider == "sentence-transformers" and embedding_model:
        embedding_kwargs["model_name"] = embedding_model

    try:
        embedding_generator = create_embedding_generator(embedding_provider, **embedding_kwargs)
    except Exception as e:
        print(f"Warning: Failed to create embedding generator: {e}")
        print("  Falling back to hash-based embeddings...")
        embedding_generator = SimpleMedLitEmbeddingGenerator()

    return IngestionOrchestrator(
        domain=domain,
        parser=JournalArticleParser(),
        entity_extractor=entity_extractor,
        entity_resolver=MedLitEntityResolver(domain=domain),
        relationship_extractor=relationship_extractor,
        embedding_generator=embedding_generator,
        entity_storage=InMemoryEntityStorage(),
        relationship_storage=InMemoryRelationshipStorage(),
        document_storage=InMemoryDocumentStorage(),
    )


async def ingest_paper_file(
    orchestrator: IngestionOrchestrator,
    file_path: Path,
    content_type: str,
) -> tuple[str, int, int]:
    """Ingest a single Paper JSON or PMC XML file.

    Args:
        orchestrator: The ingestion orchestrator.
        file_path: Path to the Paper JSON or PMC XML file.
        content_type: Content type ("application/json" or "application/xml").

    Returns:
        Tuple of (document_id, entities_extracted, relationships_extracted).
    """
    try:
        # Read file
        with open(file_path, "rb") as f:
            raw_content = f.read()

        # Ingest the paper
        result = await orchestrator.ingest_document(
            raw_content=raw_content,
            content_type=content_type,
            source_uri=str(file_path),
        )

        return (result.document_id, result.entities_extracted, result.relationships_extracted)

    except Exception as e:
        print(f"  ERROR processing {file_path.name}: {e}")
        return (file_path.stem, 0, 0)


async def main() -> None:
    """Main ingestion function."""
    parser = argparse.ArgumentParser(description="Ingest medical literature papers and generate bundle")
    parser.add_argument(
        "--input-dir",
        type=str,
        required=True,
        help="Directory containing Paper JSON files or PMC XML files",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="medlit_bundle",
        help="Output directory for the bundle (default: medlit_bundle)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of papers to process (for testing)",
    )
    parser.add_argument(
        "--content-type",
        type=str,
        choices=["json", "xml"],
        default="json",
        help="Input file format: json (Paper JSON) or xml (PMC XML)",
    )
    parser.add_argument(
        "--ner-provider",
        type=str,
        choices=["none", "biobert", "scispacy", "ollama"],
        default="none",
        help="NER provider for entity extraction (default: none, uses pre-extracted entities)",
    )
    parser.add_argument(
        "--ner-model",
        type=str,
        default=None,
        help="NER model name (provider-specific, e.g., 'llama3.1:8b' for Ollama)",
    )
    parser.add_argument(
        "--ner-host",
        type=str,
        default=None,
        help="Ollama host URL for NER (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--embedding-provider",
        type=str,
        choices=["hash", "ollama", "sentence-transformers"],
        default="hash",
        help="Embedding provider (default: hash)",
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default=None,
        help="Embedding model name (e.g., 'nomic-embed-text' for Ollama)",
    )
    parser.add_argument(
        "--embedding-host",
        type=str,
        default=None,
        help="Ollama host URL for embeddings (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--use-pattern-extraction",
        action="store_true",
        default=True,
        help="Enable pattern-based relationship extraction (default: True)",
    )
    parser.add_argument(
        "--no-pattern-extraction",
        action="store_false",
        dest="use_pattern_extraction",
        help="Disable pattern-based relationship extraction",
    )
    parser.add_argument(
        "--use-llm-extraction",
        action="store_true",
        default=False,
        help="Enable LLM-based relationship extraction",
    )
    parser.add_argument(
        "--llm-provider",
        type=str,
        choices=["ollama", "openai"],
        default="ollama",
        help="LLM provider for relationship extraction (default: ollama)",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default="llama3.1:8b",
        help="LLM model name (default: llama3.1:8b)",
    )
    parser.add_argument(
        "--llm-host",
        type=str,
        default="http://localhost:11434",
        help="LLM host URL for Ollama (default: http://localhost:11434)",
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        print(f"ERROR: Input directory does not exist: {input_dir}")
        return

    # Find all files based on content type
    if args.content_type == "json":
        files = sorted(input_dir.glob("*.json"))
        content_type = "application/json"
    else:
        files = sorted(input_dir.glob("*.xml"))
        content_type = "application/xml"

    if args.limit:
        files = files[: args.limit]

    if not files:
        print(f"ERROR: No {args.content_type.upper()} files found in {input_dir}")
        return

    print("=" * 60)
    print("Medical Literature Knowledge Graph - Ingestion Pipeline")
    print("=" * 60)
    print(f"\nInput directory: {input_dir}")
    print(f"Found {len(files)} paper(s) to process")
    if args.limit:
        print(f"(Limited to {args.limit} papers)")

    print("\n[1/3] Initializing pipeline...")
    print(f"  NER provider: {args.ner_provider}")
    print(f"  Embedding provider: {args.embedding_provider}")
    print(f"  Pattern extraction: {args.use_pattern_extraction}")
    print(f"  LLM extraction: {args.use_llm_extraction}")

    orchestrator = build_orchestrator(
        ner_provider=args.ner_provider,
        ner_model=args.ner_model,
        ner_host=args.ner_host,
        embedding_provider=args.embedding_provider,
        embedding_model=args.embedding_model,
        embedding_host=args.embedding_host,
        use_pattern_extraction=args.use_pattern_extraction,
        use_llm_extraction=args.use_llm_extraction,
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
        llm_host=args.llm_host,
    )
    entity_storage = orchestrator.entity_storage
    relationship_storage = orchestrator.relationship_storage
    document_storage = orchestrator.document_storage

    print("\n[2/3] Ingesting papers...")
    total_entities = 0
    total_relationships = 0
    processed = 0
    errors = 0

    for file_path in files:
        doc_id, entities, relationships = await ingest_paper_file(orchestrator, file_path, content_type)
        if entities > 0 or relationships > 0:
            print(f"  {file_path.name}: {entities} entities, {relationships} relationships")
            total_entities += entities
            total_relationships += relationships
            processed += 1
        else:
            errors += 1

    print(f"\n[3/3] Exporting bundle...")
    print(f"  Processed: {processed} papers")
    print(f"  Errors/skipped: {errors} papers")
    print(f"  Total entities: {total_entities}")
    print(f"  Total relationships: {total_relationships}")

    # Get final counts from storage
    doc_count = await document_storage.count()
    ent_count = await entity_storage.count()
    rel_count = await relationship_storage.count()

    print(f"\nFinal counts:")
    print(f"  Documents: {doc_count}")
    print(f"  Entities: {ent_count}")
    print(f"  Relationships: {rel_count}")

    # Create bundle
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create a simple README for the bundle
    with TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)
        readme_file = temp_path / "README.md"
        readme_content = f"""# Medical Literature Knowledge Graph Bundle

This bundle contains extracted knowledge from biomedical journal articles.

## Statistics

- Papers processed: {processed}
- Total entities: {ent_count}
- Total relationships: {rel_count}

## Domain

- Domain: medlit
- Entity types: disease, gene, drug, protein, symptom, procedure, biomarker, pathway
- Relationship types: treats, causes, increases_risk, associated_with, interacts_with, etc.

## Source

Papers were processed from {args.content_type.upper()} format.
"""
        readme_file.write_text(readme_content)

        # Export the bundle
        await write_bundle(
            entity_storage=entity_storage,
            relationship_storage=relationship_storage,
            bundle_path=output_dir,
            domain="medlit",
            label="medical-literature",
            docs=temp_path,
            description="Knowledge graph bundle of biomedical journal articles",
        )

    print(f"\n✓ Bundle exported to: {output_dir}")
    print(f"  - manifest.json")
    print(f"  - entities.jsonl")
    print(f"  - relationships.jsonl")
    print(f"  - documents.jsonl (if docs provided)")
    print(f"  - docs/ (documentation)")


if __name__ == "__main__":
    asyncio.run(main())
