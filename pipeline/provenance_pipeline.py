#!/usr/bin/env python3
"""
Stage 2: Provenance Extraction Pipeline

This pipeline extracts paper-level metadata and document structure from PMC XML files.

Database: provenance.db (SQLite)
Tables: papers, sections, paragraphs, citations

This enables:
- Tracing claims back to specific paragraphs
- Evidence of attribution (who made the claim?)
- Temporal analysis (when was it published?)
- Citation network analysis

Usage:
    python pmc_provenance_pipeline.py --xml-dir pmc_xmls --output-dir output
"""

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET

from pydantic import BaseModel, Field


# ============================================================================
# Pydantic Models for Provenance Data
# ============================================================================


class Author(BaseModel):
    """Represents a paper author."""

    surname: str = Field(..., description="Author's last name")
    given_names: Optional[str] = Field(None, description="Author's first/middle name(s)")
    affiliation: Optional[str] = Field(None, description="Author's institutional affiliation")

    def full_name(self) -> str:
        """Return formatted full name."""
        if self.given_names:
            return f"{self.surname} {self.given_names}"
        return self.surname


class Paper(BaseModel):
    """Represents paper metadata."""

    pmc_id: str = Field(..., description="PubMed Central ID")
    pmid: Optional[str] = Field(None, description="PubMed ID")
    title: str = Field(..., description="Article title")
    journal: str = Field(..., description="Journal name")
    pub_date: Optional[str] = Field(None, description="Publication date (YYYY-MM-DD format)")
    authors: list[Author] = Field(default_factory=list, description="List of authors")
    doi: Optional[str] = Field(None, description="Digital Object Identifier")
    keywords: list[str] = Field(default_factory=list, description="Article keywords")
    abstract_text: Optional[str] = Field(None, description="Abstract text")


class Section(BaseModel):
    """Represents a document section."""

    section_id: str = Field(..., description="Unique section identifier (e.g., PMC322947_abstract)")
    paper_id: str = Field(..., description="PMC ID of parent paper")
    section_type: str = Field(..., description="Type: abstract, intro, methods, results, discussion, conclusion")
    section_order: int = Field(..., description="Order within document")
    title: Optional[str] = Field(None, description="Section title")


class Paragraph(BaseModel):
    """Represents a paragraph within a section."""

    paragraph_id: str = Field(..., description="Unique paragraph identifier (e.g., PMC322947_abstract_p1)")
    section_id: str = Field(..., description="Parent section ID")
    paragraph_order: int = Field(..., description="Order within section")
    text: str = Field(..., description="Paragraph text content")
    start_char: int = Field(..., description="Starting character position in full document")
    end_char: int = Field(..., description="Ending character position in full document")


class Citation(BaseModel):
    """Represents a citation reference."""

    citing_paper: str = Field(..., description="PMC ID of citing paper")
    cited_reference: str = Field(..., description="PMID, DOI, or freetext reference")
    context: Optional[str] = Field(None, description="Sentence or text containing the citation")
    paragraph_id: Optional[str] = Field(None, description="Paragraph containing the citation")


# ============================================================================
# XML Parsing Functions
# ============================================================================


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
                        authors.append(Author(surname=surname, given_names=given_names))

        # Extract abstract
        abstract_elem = article_meta.find(".//abstract")
        abstract_text = None
        if abstract_elem is not None:
            # Get all text content, excluding section titles if present
            abstract_parts = []
            for p in abstract_elem.findall(".//p"):
                p_text = "".join(p.itertext()).strip()
                if p_text:
                    abstract_parts.append(p_text)
            abstract_text = " ".join(abstract_parts) if abstract_parts else None

        # Extract keywords
        keywords = []
        kwd_group = article_meta.find(".//kwd-group")
        if kwd_group is not None:
            for kwd in kwd_group.findall(".//kwd"):
                kwd_text = "".join(kwd.itertext()).strip()
                if kwd_text:
                    keywords.append(kwd_text)

        return Paper(
            pmc_id=pmc_id,
            pmid=pmid,
            title=title,
            journal=journal,
            pub_date=pub_date,
            authors=authors,
            doi=doi,
            keywords=keywords,
            abstract_text=abstract_text,
        )

    except ET.ParseError as e:
        print(f"Error parsing {xml_path}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error parsing {xml_path}: {e}")
        return None


def extract_sections_and_paragraphs(xml_path: Path, paper_id: str) -> tuple[list[Section], list[Paragraph]]:
    """
    Extract document sections and paragraphs from PMC XML.

    Args:
        xml_path: Path to PMC XML file
        paper_id: PMC ID of the paper

    Returns:
        Tuple of (sections list, paragraphs list)
    """
    sections = []
    paragraphs = []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        article = root.find(".//article")
        if article is None:
            return sections, paragraphs

        char_position = 0  # Track character position in full document
        section_order = 0

        # Process abstract as first section
        front = article.find("front")
        if front is not None:
            abstract_elem = front.find(".//abstract")
            if abstract_elem is not None:
                section_id = f"{paper_id}_abstract"
                sections.append(
                    Section(
                        section_id=section_id,
                        paper_id=paper_id,
                        section_type="abstract",
                        section_order=section_order,
                        title="Abstract",
                    )
                )

                # Extract paragraphs from abstract
                para_order = 0
                for p_elem in abstract_elem.findall(".//p"):
                    text = "".join(p_elem.itertext()).strip()
                    if text:
                        para_id = f"{section_id}_p{para_order}"
                        start_char = char_position
                        end_char = start_char + len(text)

                        paragraphs.append(
                            Paragraph(
                                paragraph_id=para_id,
                                section_id=section_id,
                                paragraph_order=para_order,
                                text=text,
                                start_char=start_char,
                                end_char=end_char,
                            )
                        )

                        char_position = end_char + 1  # +1 for paragraph break
                        para_order += 1

                section_order += 1

        # Process body sections
        body = article.find(".//body")
        if body is not None:
            for sec_elem in body.findall(".//sec"):
                # Get section title
                title_elem = sec_elem.find("title")
                title = "".join(title_elem.itertext()).strip() if title_elem is not None else None

                # Infer section type from title
                section_type = infer_section_type(title) if title else "body"

                section_id = f"{paper_id}_sec{section_order}"
                sections.append(
                    Section(
                        section_id=section_id,
                        paper_id=paper_id,
                        section_type=section_type,
                        section_order=section_order,
                        title=title,
                    )
                )

                # Extract paragraphs
                para_order = 0
                for p_elem in sec_elem.findall(".//p"):
                    text = "".join(p_elem.itertext()).strip()
                    if text:
                        para_id = f"{section_id}_p{para_order}"
                        start_char = char_position
                        end_char = start_char + len(text)

                        paragraphs.append(
                            Paragraph(
                                paragraph_id=para_id,
                                section_id=section_id,
                                paragraph_order=para_order,
                                text=text,
                                start_char=start_char,
                                end_char=end_char,
                            )
                        )

                        char_position = end_char + 1
                        para_order += 1

                section_order += 1

    except ET.ParseError as e:
        print(f"Error parsing sections from {xml_path}: {e}")
    except Exception as e:
        print(f"Unexpected error extracting sections from {xml_path}: {e}")

    return sections, paragraphs


def infer_section_type(title: Optional[str]) -> str:
    """
    Infer section type from section title.

    Args:
        title: Section title text

    Returns:
        Section type: intro, methods, results, discussion, conclusion, or body
    """
    if not title:
        return "body"

    title_lower = title.lower()

    if "introduction" in title_lower or "background" in title_lower:
        return "intro"
    elif "method" in title_lower or "material" in title_lower:
        return "methods"
    elif "result" in title_lower or "finding" in title_lower:
        return "results"
    elif "discussion" in title_lower or "interpretation" in title_lower:
        return "discussion"
    elif "conclusion" in title_lower or "summary" in title_lower:
        return "conclusion"
    else:
        return "body"


# ============================================================================
# Database Functions
# ============================================================================


def create_provenance_db(db_path: Path) -> sqlite3.Connection:
    """
    Create provenance database with schema.

    Args:
        db_path: Path to database file

    Returns:
        SQLite connection
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create papers table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS papers (
            pmc_id TEXT PRIMARY KEY,
            pmid TEXT,
            title TEXT,
            journal TEXT,
            pub_date DATE,
            authors TEXT,  -- JSON array
            doi TEXT,
            keywords TEXT,  -- JSON array
            abstract_text TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Create sections table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sections (
            section_id TEXT PRIMARY KEY,
            paper_id TEXT REFERENCES papers(pmc_id) ON DELETE CASCADE,
            section_type TEXT,
            section_order INTEGER,
            title TEXT
        )
    """
    )

    # Create paragraphs table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS paragraphs (
            paragraph_id TEXT PRIMARY KEY,
            section_id TEXT REFERENCES sections(section_id) ON DELETE CASCADE,
            paragraph_order INTEGER,
            text TEXT,
            start_char INTEGER,
            end_char INTEGER
        )
    """
    )

    # Create citations table (for future use)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS citations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            citing_paper TEXT REFERENCES papers(pmc_id),
            cited_reference TEXT,
            context TEXT,
            paragraph_id TEXT REFERENCES paragraphs(paragraph_id)
        )
    """
    )

    # Create indexes for common queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sections_paper_id ON sections(paper_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_paragraphs_section_id ON paragraphs(section_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_citations_citing_paper ON citations(citing_paper)")

    conn.commit()
    return conn


def insert_paper(conn: sqlite3.Connection, paper: Paper) -> None:
    """Insert paper into database."""
    cursor = conn.cursor()

    # Serialize authors to JSON
    authors_json = json.dumps([author.model_dump() for author in paper.authors])

    # Serialize keywords to JSON
    keywords_json = json.dumps(paper.keywords)

    cursor.execute(
        """
        INSERT OR REPLACE INTO papers
        (pmc_id, pmid, title, journal, pub_date, authors, doi, keywords, abstract_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            paper.pmc_id,
            paper.pmid,
            paper.title,
            paper.journal,
            paper.pub_date,
            authors_json,
            paper.doi,
            keywords_json,
            paper.abstract_text,
        ),
    )

    conn.commit()


def insert_sections(conn: sqlite3.Connection, sections: list[Section]) -> None:
    """Insert sections into database."""
    cursor = conn.cursor()

    for section in sections:
        cursor.execute(
            """
            INSERT OR REPLACE INTO sections
            (section_id, paper_id, section_type, section_order, title)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                section.section_id,
                section.paper_id,
                section.section_type,
                section.section_order,
                section.title,
            ),
        )

    conn.commit()


def insert_paragraphs(conn: sqlite3.Connection, paragraphs: list[Paragraph]) -> None:
    """Insert paragraphs into database."""
    cursor = conn.cursor()

    for para in paragraphs:
        cursor.execute(
            """
            INSERT OR REPLACE INTO paragraphs
            (paragraph_id, section_id, paragraph_order, text, start_char, end_char)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                para.paragraph_id,
                para.section_id,
                para.paragraph_order,
                para.text,
                para.start_char,
                para.end_char,
            ),
        )

    conn.commit()


# ============================================================================
# Main Pipeline
# ============================================================================


def process_xml_file(xml_path: Path, conn: sqlite3.Connection) -> bool:
    """
    Process a single PMC XML file and extract provenance data.

    Args:
        xml_path: Path to XML file
        conn: Database connection

    Returns:
        True if successful, False otherwise
    """
    print(f"Processing {xml_path.name}...")

    # Parse paper metadata
    paper = parse_pmc_xml(xml_path)
    if paper is None:
        print("  Failed to parse paper metadata")
        return False

    print(f"  PMC ID: {paper.pmc_id}")
    print(f"  Title: {paper.title[:60]}...")
    print(f"  Authors: {len(paper.authors)}")

    # Insert paper
    insert_paper(conn, paper)

    # Extract sections and paragraphs
    sections, paragraphs = extract_sections_and_paragraphs(xml_path, paper.pmc_id)

    print(f"  Sections: {len(sections)}")
    print(f"  Paragraphs: {len(paragraphs)}")

    # Insert sections and paragraphs
    insert_sections(conn, sections)
    insert_paragraphs(conn, paragraphs)

    return True


def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(description="Stage 2: Provenance Extraction Pipeline")
    parser.add_argument("--xml-dir", type=str, default="pmc_xmls", help="Directory containing PMC XML files")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory for database")

    args = parser.parse_args()

    xml_dir = Path(args.xml_dir)
    output_dir = Path(args.output_dir)

    # Validate input
    if not xml_dir.exists():
        print(f"Error: XML directory not found: {xml_dir}")
        return 1

    # Create output directory
    output_dir.mkdir(exist_ok=True)

    # Create database
    db_path = output_dir / "provenance.db"
    print(f"Creating provenance database: {db_path}")
    conn = create_provenance_db(db_path)

    # Process all XML files
    xml_files = sorted(xml_dir.glob("*.xml"))
    print(f"\nFound {len(xml_files)} XML files\n")

    success_count = 0
    for xml_path in xml_files:
        if process_xml_file(xml_path, conn):
            success_count += 1
        print()

    conn.close()

    # Print summary
    print("=" * 60)
    print("Provenance extraction complete!")
    print(f"Successfully processed: {success_count}/{len(xml_files)} files")
    print(f"Database: {db_path}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
