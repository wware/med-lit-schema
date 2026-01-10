#!/usr/bin/env python3
"""
Stage 2: Provenance Extraction Ingest

This ingest extracts paper-level metadata and document structure from source files.
Uses parser and storage interfaces for flexible format and backend support.

Usage:
    python provenance_pipeline.py --xml-dir pmc_xmls --output-dir output --storage sqlite
    python provenance_pipeline.py --xml-dir pmc_xmls --output-dir output --storage postgres --database-url postgresql://...
    python provenance_pipeline.py --xml-dir pmc_xmls --output-dir output --parser custom.MyParser

Custom Parser Example:
    # Create my_parser.py
    from med_lit_schema.ingest.parser_interfaces import PaperParserInterface
    class MyCustomParser(PaperParserInterface):
        @property
        def format_name(self) -> str:
            return "My Format"
        def parse_file(self, file_path: Path) -> Optional[Paper]:
            # Your parsing logic here
            pass
"""

import argparse
from pathlib import Path
from typing import Optional

# Import new schema and interfaces
try:
    from ..storage.interfaces import PipelineStorageInterface
    from ..storage.backends.sqlite import SQLitePipelineStorage
    from ..storage.backends.postgres import PostgresPipelineStorage
    from .parser_interfaces import PaperParserInterface
    from .pmc_parser import PMCXMLParser
except ImportError:
    # Absolute imports for standalone execution
    from med_lit_schema.storage.interfaces import PipelineStorageInterface
    from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage
    from med_lit_schema.storage.backends.postgres import PostgresPipelineStorage
    from med_lit_schema.ingest.parser_interfaces import PaperParserInterface
    from med_lit_schema.ingest.pmc_parser import PMCXMLParser

from med_lit_schema.entity import Paper


def parse_pmc_xml(xml_path: Path) -> Optional["Paper"]:
    """
    Parse PMC XML file and extract paper metadata.

    DEPRECATED: Use PMCXMLParser class directly for better control.
    This function is kept for backward compatibility.

    Args:
        xml_path: Path to PMC XML file

    Returns:
        Paper object with extracted metadata, or None if parsing fails

    Example:

        >>> from pathlib import Path
        >>> paper = parse_pmc_xml(Path("PMC123456.xml"))
        >>> if paper:
        ...     print(paper.title)
    """
    parser = PMCXMLParser()
    return parser.parse_file(xml_path)


def main():
    """Main ingest execution."""
    arg_parser = argparse.ArgumentParser(description="Stage 2: Provenance Extraction Pipeline")
    arg_parser.add_argument("--input-dir", type=str, default="pmc_xmls", help="Directory containing input files")
    arg_parser.add_argument("--file-pattern", type=str, default="*.xml", help="Glob pattern for input files")
    arg_parser.add_argument("--output-dir", type=str, default="output", help="Output directory")
    arg_parser.add_argument("--storage", type=str, choices=["sqlite", "postgres"], default="sqlite", help="Storage backend to use")
    arg_parser.add_argument("--database-url", type=str, default=None, help="Database URL for PostgreSQL (required if --storage=postgres)")
    arg_parser.add_argument("--parser", type=str, default="pmc", help="Parser to use: 'pmc' or module.ClassName for custom parser")
    arg_parser.add_argument("--json-output-dir", type=str, default=None, help="Optional directory to save parsed papers as JSON files")

    args = arg_parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    json_output_dir: Optional[Path] = None
    if args.json_output_dir:
        json_output_dir = Path(args.json_output_dir)
        json_output_dir.mkdir(exist_ok=True)

    # Validate input
    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}")
        return 1

    # Initialize parser
    paper_parser: PaperParserInterface
    if args.parser == "pmc":
        paper_parser = PMCXMLParser()
    else:
        # Load custom parser from module path
        try:
            module_path, class_name = args.parser.rsplit(".", 1)
            import importlib

            module = importlib.import_module(module_path)
            parser_class = getattr(module, class_name)
            paper_parser = parser_class()
            if not isinstance(paper_parser, PaperParserInterface):
                print(f"Error: {args.parser} does not implement PaperParserInterface")
                return 1
        except (ValueError, ImportError, AttributeError) as e:
            print(f"Error loading custom parser '{args.parser}': {e}")
            return 1

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

    # Process all input files
    print(f"\nUsing parser: {paper_parser.format_name}")
    print(f"Processing files from: {input_dir}")
    print()

    success_count = 0
    total_count = 0
    for file_path, paper in paper_parser.parse_directory(input_dir, args.file_pattern):
        total_count += 1
        print(f"Processing {file_path.name}...")

        if paper is None:
            print("  Failed to parse file")
            continue

        print(f"  Paper ID: {paper.paper_id}")
        print(f"  Title: {paper.title[:60]}...")
        print(f"  Authors: {len(paper.authors)}")

        # Store paper using storage interface
        storage.papers.add_paper(paper)

        # Optionally save as JSON
        if json_output_dir:
            json_file_path = json_output_dir / f"{paper.paper_id}.json"
            with open(json_file_path, "w") as f:
                f.write(paper.model_dump_json(indent=2))
            print(f"  Saved JSON to {json_file_path.name}")

        success_count += 1
        print()

    # Clean up
    storage.close()

    # Print summary
    print("=" * 60)
    print("Provenance extraction complete!")
    print(f"Successfully processed: {success_count}/{total_count} files")
    print(f"Storage: {args.storage}")
    print(f"Paper count: {storage.papers.paper_count}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
