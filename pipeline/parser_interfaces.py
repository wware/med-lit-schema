"""
Parser interfaces for extracting paper metadata from various sources.

These ABC interfaces allow the pipeline to work with different input formats:
- PMC XML files
- PubMed XML
- JSON APIs (Semantic Scholar, CrossRef, etc.)
- PDF extraction
- Custom formats

All parsers produce Paper objects using the domain models from entity.py.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Iterator

from med_lit_schema.entity import Paper


class PaperParserInterface(ABC):
    """
    Abstract interface for parsing papers from various sources.

    Implementations should extract metadata and content from their specific
    format and return standardized Paper objects.

    Attributes:

        format_name: Human-readable name of the format (e.g., "PMC XML", "PubMed JSON")

    """

    @property
    @abstractmethod
    def format_name(self) -> str:
        """
        Human-readable name of the format this parser handles.

        Example:

            >>> parser.format_name
            'PMC XML'
        """
        pass

    @abstractmethod
    def parse_file(self, file_path: Path) -> Optional[Paper]:
        """
        Parse a single file and extract paper metadata.

        Attributes:

            file_path: Path to the file to parse

        Returns:
            Paper object with extracted metadata, or None if parsing fails
        """
        pass

    def parse_directory(self, directory: Path, pattern: str = "*") -> Iterator[tuple[Path, Optional[Paper]]]:
        """
        Parse all matching files in a directory.

        Default implementation uses glob and calls parse_file for each match.
        Override if you need custom directory traversal logic.

        Attributes:

            directory: Directory containing files to parse
            pattern: Glob pattern for matching files (default: "*")

        Yields:
            Tuples of (file_path, paper_or_none) for each file

        Example:

            >>> for path, paper in parser.parse_directory(Path("xmls"), "*.xml"):
            ...     if paper:
            ...         print(f"Parsed {paper.title}")
        """
        for file_path in directory.glob(pattern):
            if file_path.is_file():
                paper = self.parse_file(file_path)
                yield (file_path, paper)

    def validate_file(self, file_path: Path) -> bool:
        """
        Check if a file is likely parseable by this parser.

        Default implementation just checks file existence.
        Override to add format-specific validation (e.g., XML schema check).

        Attributes:

            file_path: Path to validate

        Returns:
            True if file appears to be parseable

        Example:

            >>> parser.validate_file(Path("paper.xml"))
            True
        """
        return file_path.exists() and file_path.is_file()


class StreamingParserInterface(ABC):
    """
    Interface for parsers that can handle streaming data.

    Use this for parsers that work with APIs, databases, or other
    non-file sources.

    Attributes:

        source_name: Name of the data source (e.g., "Semantic Scholar API")

    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name of the data source."""
        pass

    @abstractmethod
    def parse_from_id(self, identifier: str) -> Optional[Paper]:
        """
        Fetch and parse a paper by its identifier.

        Attributes:

            identifier: Paper identifier (e.g., DOI, PMID, PMC ID)

        Returns:
            Paper object or None if not found/parseable
        """
        pass

    def parse_batch(self, identifiers: list[str]) -> Iterator[tuple[str, Optional[Paper]]]:
        """
        Parse multiple papers by their identifiers.

        Default implementation calls parse_from_id for each ID.
        Override for batch API optimization.

        Attributes:

            identifiers: List of paper identifiers

        Yields:
            Tuples of (identifier, paper_or_none)
        """
        for identifier in identifiers:
            paper = self.parse_from_id(identifier)
            yield (identifier, paper)
