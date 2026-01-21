"""Document parser for journal articles.

Converts raw paper input (PMC XML, JSON, etc.) into JournalArticle documents.
Ports logic from med-lit-schema's ingest/pmc_parser.py.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from kgraph.pipeline.interfaces import DocumentParserInterface

from ..domain.documents import JournalArticle


class JournalArticleParser(DocumentParserInterface):
    """Parse raw journal article content into JournalArticle documents.

    This parser handles various input formats (PMC XML, JSON from med-lit-schema)
    and converts them to kgraph's JournalArticle format.

    Ports logic from med-lit-schema's ingest/pmc_parser.py for PMC XML parsing.
    """

    async def parse(
        self,
        raw_content: bytes,
        content_type: str,
        source_uri: str | None = None,
    ) -> JournalArticle:
        """Parse raw content into a JournalArticle.

        Args:
            raw_content: Raw document bytes (may be JSON, XML, etc.)
            content_type: MIME type or format indicator
            source_uri: Optional URI identifying the document's origin

        Returns:
            A JournalArticle instance ready for entity and relationship extraction.

        Raises:
            ValueError: If content_type is unsupported or content is malformed.
        """
        if content_type == "application/json":
            # Parse JSON (e.g., from med-lit-schema's Paper format)
            import json

            data = json.loads(raw_content.decode("utf-8"))
            return self._parse_from_dict(data, source_uri)

        elif content_type == "application/xml" or content_type == "text/xml":
            # Parse PMC XML
            return self._parse_pmc_xml(raw_content, source_uri)

        else:
            raise ValueError(f"Unsupported content_type: {content_type}")

    def _parse_from_dict(self, data: dict[str, Any], source_uri: str | None) -> JournalArticle:
        """Parse from a dictionary (e.g., med-lit-schema's Paper format).

        Maps Paper fields to JournalArticle:
        - paper_id → document_id (prefer doi:, else pmid:, else paper_id)
        - title → title
        - abstract → abstract
        - abstract (+ optional full_text) → content
        - authors → authors
        - publication_date → publication_date
        - journal → journal
        - doi → doi
        - pmid → pmid
        - metadata → metadata (study_type, sample_size, mesh_terms, etc.)
        - extraction_provenance → metadata["extraction"]
        """
        # Determine document_id (prefer DOI, else PMID, else paper_id)
        paper_id = data.get("paper_id", "")
        doi = data.get("doi")
        pmid = data.get("pmid")

        if doi:
            document_id = f"doi:{doi}"
        elif pmid:
            document_id = f"pmid:{pmid}"
        elif paper_id:
            document_id = paper_id
        else:
            raise ValueError("No valid identifier found (paper_id, doi, or pmid required)")

        # Extract content (abstract + optional full text)
        abstract = data.get("abstract", "")
        full_text = data.get("full_text", "")  # May not be present
        content = abstract
        if full_text:
            content = f"{abstract}\n\n{full_text}" if abstract else full_text

        # Extract metadata
        metadata: dict[str, Any] = {}

        # Map PaperMetadata fields
        paper_metadata = data.get("metadata", {})
        if isinstance(paper_metadata, dict):
            metadata.update(paper_metadata)
        else:
            # If metadata is a PaperMetadata object (already parsed), extract its fields
            if hasattr(paper_metadata, "study_type"):
                metadata["study_type"] = paper_metadata.study_type
            if hasattr(paper_metadata, "sample_size"):
                metadata["sample_size"] = paper_metadata.sample_size
            if hasattr(paper_metadata, "mesh_terms"):
                metadata["mesh_terms"] = paper_metadata.mesh_terms

        # Store extraction provenance if present
        extraction_provenance = data.get("extraction_provenance")
        if extraction_provenance:
            metadata["extraction"] = extraction_provenance

        # Store entities and relationships in metadata so extractors can find them
        if "entities" in data:
            metadata["entities"] = data["entities"]
        if "relationships" in data:
            metadata["relationships"] = data["relationships"]

        # Extract authors (handle both list and string formats)
        authors = data.get("authors", [])
        if isinstance(authors, str):
            authors = [authors]
        elif not isinstance(authors, list):
            authors = []

        return JournalArticle(
            document_id=document_id,
            title=data.get("title", ""),
            content=content,
            content_type="text/plain",  # Processed text
            source_uri=source_uri,
            created_at=datetime.now(timezone.utc),
            authors=tuple(authors),
            abstract=abstract,
            publication_date=data.get("publication_date"),
            journal=data.get("journal"),
            doi=doi,
            pmid=pmid,
            metadata=metadata,
        )

    def _parse_pmc_xml(self, raw_content: bytes, source_uri: str | None) -> JournalArticle:
        """Parse PMC XML (JATS format) into JournalArticle.

        Ports logic from med-lit-schema's ingest/pmc_parser.py.
        """
        try:
            root = ET.fromstring(raw_content)

            # Find article element
            article = root.find(".//article")
            if article is None:
                raise ValueError("No <article> element found in XML")

            # Extract metadata from <front> section
            front = article.find("front")
            if front is None:
                raise ValueError("No <front> element found in XML")

            article_meta = front.find(".//article-meta")
            if article_meta is None:
                raise ValueError("No <article-meta> element found in XML")

            # Extract identifiers
            pmc_id = self._extract_pmc_id(article_meta, source_uri)
            pmid = self._extract_pmid(article_meta)
            doi = self._extract_doi(article_meta)

            # Extract bibliographic metadata
            title = self._extract_title(article_meta)
            journal = self._extract_journal(front)
            pub_date = self._extract_publication_date(article_meta)
            authors = self._extract_authors(article_meta)
            abstract = self._extract_abstract(article_meta)
            mesh_terms = self._extract_mesh_terms(article_meta)

            # Extract full text from body
            body = article.find(".//body")
            full_text = ""
            if body is not None:
                full_text = " ".join("".join(p.itertext()) for p in body.findall(".//p"))

            # Determine document_id (prefer DOI, else PMID, else PMC ID)
            if doi:
                document_id = f"doi:{doi}"
            elif pmid:
                document_id = f"pmid:{pmid}"
            else:
                document_id = pmc_id

            # Combine abstract and full text for content
            content = abstract
            if full_text:
                content = f"{abstract}\n\n{full_text}" if abstract else full_text

            # Build metadata
            metadata: dict[str, Any] = {
                "mesh_terms": mesh_terms,
                "publication_date": pub_date,
                "journal": journal,
            }

            return JournalArticle(
                document_id=document_id,
                title=title,
                content=content,
                content_type="text/plain",
                source_uri=source_uri,
                created_at=datetime.now(timezone.utc),
                authors=tuple(authors),
                abstract=abstract,
                publication_date=pub_date,
                journal=journal,
                doi=doi,
                pmid=pmid,
                metadata=metadata,
            )

        except ET.ParseError as e:
            raise ValueError(f"Error parsing PMC XML: {e}") from e
        except Exception as e:
            raise ValueError(f"Unexpected error parsing PMC XML: {e}") from e

    # Helper methods for PMC XML extraction (ported from med-lit-schema)

    def _extract_pmc_id(self, article_meta, source_uri: str | None) -> str:
        """Extract PMC ID from article metadata."""
        pmc_id_elem = article_meta.find(".//article-id[@pub-id-type='pmcid']")
        if pmc_id_elem is not None and pmc_id_elem.text:
            return pmc_id_elem.text
        # Fallback: try to extract from source_uri or use stem
        if source_uri:
            # Try to extract PMC ID from filename like "PMC123456.xml"
            import re

            match = re.search(r"PMC\d+", source_uri)
            if match:
                return match.group()
        return "unknown"

    def _extract_pmid(self, article_meta) -> str | None:
        """Extract PubMed ID from article metadata."""
        pmid_elem = article_meta.find(".//article-id[@pub-id-type='pmid']")
        return pmid_elem.text if pmid_elem is not None and pmid_elem.text else None

    def _extract_doi(self, article_meta) -> str | None:
        """Extract DOI from article metadata."""
        doi_elem = article_meta.find(".//article-id[@pub-id-type='doi']")
        return doi_elem.text if doi_elem is not None and doi_elem.text else None

    def _extract_title(self, article_meta) -> str:
        """Extract article title."""
        title_elem = article_meta.find(".//article-title")
        return "".join(title_elem.itertext()).strip() if title_elem is not None else "Untitled"

    def _extract_journal(self, front) -> str:
        """Extract journal name."""
        journal_meta = front.find(".//journal-meta")
        journal_elem = journal_meta.find(".//journal-title") if journal_meta is not None else None
        return "".join(journal_elem.itertext()).strip() if journal_elem is not None else "Unknown Journal"

    def _extract_publication_date(self, article_meta) -> str | None:
        """Extract publication date in YYYY-MM-DD format."""
        pub_date_elem = article_meta.find(".//pub-date[@pub-type='ppub']")
        if pub_date_elem is None:
            pub_date_elem = article_meta.find(".//pub-date")

        if pub_date_elem is None:
            return None

        year = pub_date_elem.find("year")
        month = pub_date_elem.find("month")
        day = pub_date_elem.find("day")

        year_str = year.text if year is not None and year.text else "0001"
        month_str = month.text if month is not None and month.text else "01"
        day_str = day.text if day is not None and day.text else "01"

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

                    surname = surname_elem.text if surname_elem is not None and surname_elem.text else ""
                    given_names = given_names_elem.text if given_names_elem is not None and given_names_elem.text else None

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
