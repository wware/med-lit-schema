# Medical Knowledge Graph Schema

A Python library for building and querying a medical literature knowledge graph with full provenance tracking.

## What is this?

This library extracts entities and relationships from PubMed/PMC papers and builds a queryable knowledge graph. Every relationship traces back to its source paper, section, and paragraph.

**Key principles:**

- **Provenance first** - All relationships include evidence with paper_id, section_type, study_type
- **Evidence quality weighting** - Confidence scores auto-calculated from study type (RCT=1.0, case_report=0.4)
- **Standards-based IDs** - UMLS for diseases, HGNC for genes, RxNorm for drugs, UniProt for proteins
- **Pydantic validation** - Runtime validation prevents invalid medical data

## Documentation Structure

This documentation is organized into three "books" for different audiences:

### [User Guide](user-guide/index.md)
For people **using** the knowledge graph. Covers installation, basic usage, querying, and API reference.

### [Developer Guide](developer-guide/index.md)
For people **contributing** to the codebase. Covers architecture, ingestion pipeline, testing, and Docker setup.

### [Research Notes](research-notes/index.md)
Working thoughts, design decisions, and experiments. Captures the "why" behind architectural choices.

## Quick Example

```python
from med_lit_schema.entity import Disease, Drug
from med_lit_schema.relationship import create_relationship
from med_lit_schema.base import PredicateType

# Create entities
disease = Disease(
    entity_id="C0006142",
    name="Breast Cancer",
    source="umls"
)

drug = Drug(
    entity_id="RxNorm:1187832",
    name="Olaparib",
    drug_class="PARP inhibitor"
)

# Create relationship with evidence
treats = create_relationship(
    PredicateType.TREATS,
    subject_id=drug.entity_id,
    object_id=disease.entity_id,
    source_papers=["PMC999"],
    confidence=0.85
)
```

## Installation

```bash
uv add med-lit-schema
```

Or for development:

```bash
git clone https://github.com/wware/med-lit-schema
cd med-lit-schema
uv sync
```
