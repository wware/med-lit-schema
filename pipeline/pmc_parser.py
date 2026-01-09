"""
PMC XML parser implementation.

Parses PubMed Central (PMC) XML files into Paper objects.
"""

from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET

from med_lit_schema.entity import (
    Paper,
    PaperMetadata,
    ExtractionProvenance,
    ExtractionPipelineInfo,
    ExecutionInfo,
    PromptInfo,
)
from med_lit_schema.pipeline.parser_interfaces import PaperParserInterface


class PMCXMLParser(PaperParserInterface):
    """
    Parser for PubMed Central (PMC) XML format.

    Extracts paper metadata including title, authors, abstract, publication
    date, and identifiers from PMC JATS XML files.

    Attributes:

        pipeline_name: Name to use in extraction provenance
        pipeline_version: Version to use in extraction provenance
        git_commit: Git commit hash for provenance tracking
        git_branch: Git branch name for provenance tracking

    Example:

        >>> parser = PMCXMLParser()
        >>> paper = parser.parse_file(Path("PMC123456.xml"))
        >>> if paper:
        ...     print(paper.title)
    """

    def __init__(
        self,
        pipeline_name: str = "pmc_xml_parser",
        pipeline_version: str = "1.0.0",
        git_commit: str = "unknown",
        git_branch: str = "unknown",
    ):
        self._pipeline_name = pipeline_name
        self._pipeline_version = pipeline_version
        self._git_commit = git_commit
        self._git_branch = git_branch

    @property
    def format_name(self) -> str:
        """Human-readable format name."""
        return "PMC XML"

    def parse_file(self, file_path: Path) -> Optional[Paper]:
        """
        Parse a PMC XML file and extract paper metadata.

        Attributes:

            file_path: Path to PMC XML file

        Returns:
            Paper object with extracted metadata, or None if parsing fails
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Find article element
            article = root.find(".//article")
            if article is None:
                print(f"Warning: No <article> element found in {file_path.name}")
                return None

            # Extract metadata from <front> section
            front = article.find("front")
            if front is None:
                print(f"Warning: No <front> element found in {file_path.name}")
                return None

            article_meta = front.find(".//article-meta")
            if article_meta is None:
                print(f"Warning: No <article-meta> element found in {file_path.name}")
                return None

            # Extract identifiers
            pmc_id = self._extract_pmc_id(article_meta, file_path)
            pmid = self._extract_pmid(article_meta)
            doi = self._extract_doi(article_meta)

            # Extract bibliographic metadata
            title = self._extract_title(article_meta)
            journal = self._extract_journal(front)
            pub_date = self._extract_publication_date(article_meta)
            authors = self._extract_authors(article_meta)
            abstract = self._extract_abstract(article_meta)
            mesh_terms = self._extract_mesh_terms(article_meta)

            # Create provenance metadata
            provenance = self._create_provenance()

            # Create Paper object
            paper = Paper(
                paper_id=pmc_id,
                pmid=pmid,
                doi=doi,
                title=title,
                abstract=abstract,
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
                extraction_provenance=provenance,
            )

            return paper

        except ET.ParseError as e:
            print(f"Error parsing {file_path}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error parsing {file_path}: {e}")
            return None

    def validate_file(self, file_path: Path) -> bool:
        """
        Validate that a file is a parseable PMC XML file.

        Checks file existence, extension, and basic XML structure.

        Attributes:

            file_path: Path to validate

        Returns:
            True if file appears to be valid PMC XML
        """
        if not file_path.exists() or not file_path.is_file():
            return False

        if file_path.suffix.lower() != ".xml":
            return False

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            # Check for article element
            return root.find(".//article") is not None
        except ET.ParseError:
            return False
        except Exception:
            return False

    # Private helper methods for extraction

    def _extract_pmc_id(self, article_meta, file_path: Path) -> str:
        """Extract PMC ID from article metadata."""
        pmc_id_elem = article_meta.find(".//article-id[@pub-id-type='pmcid']")
        return pmc_id_elem.text if pmc_id_elem is not None else file_path.stem

    def _extract_pmid(self, article_meta) -> Optional[str]:
        """Extract PubMed ID from article metadata."""
        pmid_elem = article_meta.find(".//article-id[@pub-id-type='pmid']")
        return pmid_elem.text if pmid_elem is not None else None

    def _extract_doi(self, article_meta) -> Optional[str]:
        """Extract DOI from article metadata."""
        doi_elem = article_meta.find(".//article-id[@pub-id-type='doi']")
        return doi_elem.text if doi_elem is not None else None

    def _extract_title(self, article_meta) -> str:
        """Extract article title."""
        title_elem = article_meta.find(".//article-title")
        return (
            "".join(title_elem.itertext()).strip()
            if title_elem is not None
            else "Untitled"
        )

    def _extract_journal(self, front) -> str:
        """Extract journal name."""
        journal_meta = front.find(".//journal-meta")
        journal_elem = (
            journal_meta.find(".//journal-title") if journal_meta is not None else None
        )
        return (
            "".join(journal_elem.itertext()).strip()
            if journal_elem is not None
            else "Unknown Journal"
        )

    def _extract_publication_date(self, article_meta) -> Optional[str]:
        """Extract publication date in YYYY-MM-DD format."""
        pub_date_elem = article_meta.find(".//pub-date[@pub-type='ppub']")
        if pub_date_elem is None:
            pub_date_elem = article_meta.find(".//pub-date")

        if pub_date_elem is None:
            return None

        year = pub_date_elem.find("year")
        month = pub_date_elem.find("month")
        day = pub_date_elem.find("day")

        year_str = year.text if year is not None else "0001"
        month_str = month.text if month is not None else "01"
        day_str = day.text if day is not None else "01"

        try:
            return f"{year_str}-{month_str.zfill(2)}-{day_str.zfill(2)}"
        except ValueError:
            return None

    def _extract_authors(self, article_meta) -> list[str]:
        """Extract author list in 'Surname, Given Names' format."""
        authors = []
        contrib_group = article_meta.find(".//contrib-group")
        if contrib_group is not None:
            for contrib in contrib_group.findall(".//contrib[@contrib-type='author']"):
                name_elem = contrib.find(".//name")
                if name_elem is not None:
                    surname_elem = name_elem.find("surname")
                    given_names_elem = name_elem.find("given-names")

                    surname = surname_elem.text if surname_elem is not None else ""
                    given_names = (
                        given_names_elem.text if given_names_elem is not None else None
                    )

                    if surname:
                        if given_names:
                            authors.append(f"{surname}, {given_names}")
                        else:
                            authors.append(surname)
        return authors

    def _extract_abstract(self, article_meta) -> str:
        """Extract abstract text."""
        abstract_elem = article_meta.find(".//abstract")
        if abstract_elem is None:
            return ""

        abstract_parts = []
        for p in abstract_elem.findall(".//p"):
            p_text = "".join(p.itertext()).strip()
            if p_text:
                abstract_parts.append(p_text)

        return " ".join(abstract_parts) if abstract_parts else ""

    def _extract_mesh_terms(self, article_meta) -> list[str]:
        """Extract MeSH terms/keywords."""
        mesh_terms = []
        kwd_group = article_meta.find(".//kwd-group")
        if kwd_group is not None:
            for kwd in kwd_group.findall(".//kwd"):
                kwd_text = "".join(kwd.itertext()).strip()
                if kwd_text:
                    mesh_terms.append(kwd_text)
        return mesh_terms

    def _create_provenance(self) -> ExtractionProvenance:
        """Create extraction provenance metadata."""
        from datetime import datetime
        import socket
        import platform

        pipeline_info = ExtractionPipelineInfo(
            name=self._pipeline_name,
            version=self._pipeline_version,
            git_commit=self._git_commit,
            git_commit_short=self._git_commit[:7] if self._git_commit != "unknown" else "unknown",
            git_branch=self._git_branch,
            git_dirty=False,
            repo_url="https://github.com/wware/med-lit-graph",
        )

        execution_info = ExecutionInfo(
            timestamp=datetime.now().isoformat(),
            hostname=socket.gethostname(),
            python_version=platform.python_version(),
            duration_seconds=None,
        )

        prompt_info = PromptInfo(version="n/a", template="n/a", checksum=None)

        return ExtractionProvenance(
            extraction_pipeline=pipeline_info,
            models={},
            prompt=prompt_info,
            execution=execution_info,
            entity_resolution=None,
        )
