#!/usr/bin/env python3
"""
Stage 2: Provenance Extraction Pipeline

This pipeline extracts paper-level metadata and document structure from PMC XML files.
Uses new schema and storage interfaces for flexible backend support.

Usage:
    python provenance_pipeline.py --xml-dir pmc_xmls --output-dir output --storage sqlite
    python provenance_pipeline.py --xml-dir pmc_xmls --output-dir output --storage postgres --database-url postgresql://...
"""

import argparse
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET

# Import new schema
try:
    from ..entity import Paper
    from .storage_interfaces import PipelineStorageInterface
    from .sqlite_storage import SQLitePipelineStorage
    from .postgres_storage import PostgresPipelineStorage
except ImportError:
    # Absolute imports for standalone execution
    from med_lit_schema.entity import Paper
    from med_lit_schema.pipeline.storage_interfaces import PipelineStorageInterface
    from med_lit_schema.pipeline.sqlite_storage import SQLitePipelineStorage
    from med_lit_schema.pipeline.postgres_storage import PostgresPipelineStorage


def parse_pmc_xml(xml_path: Path) -> Optional[Paper]:
    """
    Parse PMC XML file and extract paper metadata.

    Args:
        xml_path: Path to PMC XML file

    Returns:
        Paper object with extracted metadata, or None if parsing fails
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Find article element
        article = root.find(".//article")
        if article is None:
            print(f"Warning: No <article> element found in {xml_path.name}")
            return None

        # Extract metadata from <front> section
        front = article.find("front")
        if front is None:
            print(f"Warning: No <front> element found in {xml_path.name}")
            return None

        article_meta = front.find(".//article-meta")
        if article_meta is None:
            print(f"Warning: No <article-meta> element found in {xml_path.name}")
            return None

        # Extract PMC ID
        pmc_id_elem = article_meta.find(".//article-id[@pub-id-type='pmcid']")
        pmc_id = pmc_id_elem.text if pmc_id_elem is not None else xml_path.stem

        # Extract PMID
        pmid_elem = article_meta.find(".//article-id[@pub-id-type='pmid']")
        pmid = pmid_elem.text if pmid_elem is not None else None

        # Extract DOI
        doi_elem = article_meta.find(".//article-id[@pub-id-type='doi']")
        doi = doi_elem.text if doi_elem is not None else None

        # Extract title
        title_elem = article_meta.find(".//article-title")
        title = "".join(title_elem.itertext()).strip() if title_elem is not None else "Untitled"

        # Extract journal name
        journal_meta = front.find(".//journal-meta")
        journal_elem = journal_meta.find(".//journal-title") if journal_meta is not None else None
        journal = "".join(journal_elem.itertext()).strip() if journal_elem is not None else "Unknown Journal"

        # Extract publication date
        pub_date_elem = article_meta.find(".//pub-date[@pub-type='ppub']")
        if pub_date_elem is None:
            pub_date_elem = article_meta.find(".//pub-date")

        pub_date = None
        if pub_date_elem is not None:
            year = pub_date_elem.find("year")
            month = pub_date_elem.find("month")
            day = pub_date_elem.find("day")

            year_str = year.text if year is not None else "0001"
            month_str = month.text if month is not None else "01"
            day_str = day.text if day is not None else "01"

            try:
                pub_date = f"{year_str}-{month_str.zfill(2)}-{day_str.zfill(2)}"
            except ValueError:
                pub_date = None

        # Extract authors
        authors = []
        contrib_group = article_meta.find(".//contrib-group")
        if contrib_group is not None:
            for contrib in contrib_group.findall(".//contrib[@contrib-type='author']"):
                name_elem = contrib.find(".//name")
                if name_elem is not None:
                    surname_elem = name_elem.find("surname")
                    given_names_elem = name_elem.find("given-names")

                    surname = surname_elem.text if surname_elem is not None else ""
                    given_names = given_names_elem.text if given_names_elem is not None else None

                    if surname:
                        # Format as "Surname, Given Names" for Paper model
                        if given_names:
                            authors.append(f"{surname}, {given_names}")
                        else:
                            authors.append(surname)

        # Extract abstract
        abstract_elem = article_meta.find(".//abstract")
        abstract_text = ""
        if abstract_elem is not None:
            # Get all text content, excluding section titles if present
            abstract_parts = []
            for p in abstract_elem.findall(".//p"):
                p_text = "".join(p.itertext()).strip()
                if p_text:
                    abstract_parts.append(p_text)
            abstract_text = " ".join(abstract_parts) if abstract_parts else ""

        # Extract keywords (MeSH terms)
        mesh_terms = []
        kwd_group = article_meta.find(".//kwd-group")
        if kwd_group is not None:
            for kwd in kwd_group.findall(".//kwd"):
                kwd_text = "".join(kwd.itertext()).strip()
                if kwd_text:
                    mesh_terms.append(kwd_text)

        # Create Paper using new schema
        # Note: Paper model requires extraction_provenance, but we'll create a minimal one
        from med_lit_schema.entity import (
            PaperMetadata,
            ExtractionProvenance,
            ExtractionPipelineInfo,
            ExecutionInfo,
        )
        from datetime import datetime
        import socket
        import platform

        pipeline_info = ExtractionPipelineInfo(
            name="provenance_pipeline", version="1.0.0", git_commit="unknown", git_commit_short="unknown", git_branch="unknown", git_dirty=False, repo_url="https://github.com/wware/med-lit-graph"
        )

        execution_info = ExecutionInfo(timestamp=datetime.now().isoformat(), hostname=socket.gethostname(), python_version=platform.python_version(), duration_seconds=None)

        extraction_provenance = ExtractionProvenance(extraction_pipeline=pipeline_info, models={}, prompt=None, execution=execution_info, entity_resolution=None)

        paper = Paper(
            paper_id=pmc_id,
            pmid=pmid,
            doi=doi,
            title=title,
            abstract=abstract_text,
            authors=authors,
            publication_date=pub_date,
            journal=journal,
            entities=[],  # Will be populated by NER pipeline
            relationships=[],  # Will be populated by claims pipeline
            metadata=PaperMetadata(
                mesh_terms=mesh_terms,
                publication_date=pub_date,
                journal=journal,
            ),
            extraction_provenance=extraction_provenance,
        )

        return paper

    except ET.ParseError as e:
        print(f"Error parsing {xml_path}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error parsing {xml_path}: {e}")
        return None


def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(description="Stage 2: Provenance Extraction Pipeline")
    parser.add_argument("--xml-dir", type=str, default="pmc_xmls", help="Directory containing PMC XML files")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory")
    parser.add_argument("--storage", type=str, choices=["sqlite", "postgres"], default="sqlite", help="Storage backend to use")
    parser.add_argument("--database-url", type=str, default=None, help="Database URL for PostgreSQL (required if --storage=postgres)")

    args = parser.parse_args()

    xml_dir = Path(args.xml_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Validate input
    if not xml_dir.exists():
        print(f"Error: XML directory not found: {xml_dir}")
        return 1

    # Initialize storage based on choice
    if args.storage == "sqlite":
        db_path = output_dir / "pipeline.db"
        storage: PipelineStorageInterface = SQLitePipelineStorage(db_path)
    elif args.storage == "postgres":
        if not args.database_url:
            print("Error: --database-url required for PostgreSQL storage")
            return 1
        storage = PostgresPipelineStorage(args.database_url)
    else:
        print(f"Error: Unknown storage backend: {args.storage}")
        return 1

    # Process all XML files
    xml_files = sorted(xml_dir.glob("*.xml"))
    print(f"\nFound {len(xml_files)} XML files\n")

    success_count = 0
    for xml_path in xml_files:
        print(f"Processing {xml_path.name}...")

        # Parse paper metadata
        paper = parse_pmc_xml(xml_path)
        if paper is None:
            print("  Failed to parse paper metadata")
            continue

        print(f"  PMC ID: {paper.paper_id}")
        print(f"  Title: {paper.title[:60]}...")
        print(f"  Authors: {len(paper.authors)}")

        # Store paper using storage interface
        storage.papers.add_paper(paper)
        success_count += 1
        print()

    # Clean up
    storage.close()

    # Print summary
    print("=" * 60)
    print("Provenance extraction complete!")
    print(f"Successfully processed: {success_count}/{len(xml_files)} files")
    print(f"Storage: {args.storage}")
    print(f"Paper count: {storage.papers.paper_count}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
