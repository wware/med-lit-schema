# Core Concepts

Understanding the fundamental concepts behind the medical knowledge graph.

## Canonical Entity IDs

### The Problem: Entity Resolution

When processing millions of medical papers, the same entity appears in many forms:

- "Type 2 Diabetes" vs "T2DM" vs "Type II Diabetes" vs "NIDDM"
- "Breast Cancer" vs "Breast Carcinoma" vs "Mammary Neoplasm"
- "BRCA1" vs "breast cancer 1" vs "BRCA1 gene"

Without canonical IDs, these would be treated as separate entities, fragmenting the knowledge graph.

### The Solution: Standards-Based IDs

Every entity has a **canonical ID** from an established medical ontology:

| Entity Type | ID System | Example |
|------------|-----------|---------|
| Disease | UMLS Concept ID | `C0011860` (Type 2 Diabetes) |
| Gene | HGNC ID | `HGNC:1100` (BRCA1) |
| Drug | RxNorm ID | `RxNorm:1187832` (Olaparib) |
| Protein | UniProt ID | `P38398` (BRCA1 protein) |
| Clinical Trial | NCT ID | `NCT01234567` |

**All mentions of the same entity across ALL papers map to the same canonical ID.**

### Why This Matters

**Without canonical IDs:**
```
"BRCA1" --[increases_risk]--> "breast cancer"
"Breast Cancer" <--[treats]-- "Lynparza"
Result: No connection found (different string representations)
```

**With canonical IDs:**
```
BRCA1 (HGNC:1100) --[increases_risk]--> Breast Cancer (C0006142)
Breast Cancer (C0006142) <--[treats]-- Olaparib (RxNorm:1187832)
Result: Olaparib found (via graph traversal)
```

## Provenance: Where Did This Come From?

**ALL medical relationships MUST include evidence. Evidence is not optional.**

Every piece of evidence specifies:

- `paper_id`: Which PMC paper
- `section_type`: Where in the paper (results, methods, discussion)
- `paragraph_idx`: Exact paragraph number
- `extraction_method`: How it was extracted (for reproducibility)
- `confidence`: Confidence in this specific piece of evidence
- `study_type`: RCT, meta-analysis, observational, etc.

### Why Provenance Matters

- Doctors don't trust AI/ML systems that can't explain their sources
- Researchers can verify and audit data quality
- Users can distinguish high-quality evidence (RCTs) from low-quality (case reports)
- Full traceability means every claim can be verified

## Evidence Quality Weighting

Confidence scores are **automatically calculated** from evidence quality, not manually assigned.

```python
study_weights = {
    'rct': 1.0,              # Randomized controlled trial (gold standard)
    'meta_analysis': 0.95,   # Systematic review
    'cohort': 0.8,           # Longitudinal observational
    'case_control': 0.7,     # Retrospective
    'observational': 0.6,    # General observation
    'case_report': 0.4,      # Single patient
    'review': 0.5            # Literature review (not systematic)
}
```

This approach is:

- **Objective and consistent** - No manual scoring
- **Transparent** - Users see evidence breakdown
- **Filterable** - Show only RCT-supported claims
- **Aligned with evidence-based medicine**

## Two Levels of Evidence

### Lightweight (minimum required)

```python
source_papers=["PMC123", "PMC456"]
confidence=0.85
```

### Rich (recommended)

```python
evidence=[
    Evidence(
        paper_id="PMC123",
        section_type="results",
        paragraph_idx=5,
        sentence_idx=2,
        text_span="Exact quote from paper",
        extraction_method="llm",
        confidence=0.90,
        study_type="rct",
        sample_size=302
    )
]
```

## Entity Types

The schema supports these entity types:

**Core Medical Entities:**

- `Disease` - Diseases and conditions (UMLS IDs)
- `Gene` - Genes (HGNC IDs)
- `Drug` - Medications and compounds (RxNorm IDs)
- `Protein` - Proteins (UniProt IDs)
- `Mutation` - Genetic variants
- `Symptom` - Clinical presentations
- `Biomarker` - Diagnostic/prognostic markers
- `Pathway` - Biological pathways
- `Procedure` - Medical procedures

**Research Metadata:**

- `Paper` - Research publications (PMC IDs)
- `Author` - Paper authors
- `ClinicalTrial` - Clinical trials

## Predicate Types

Relationships use a rich vocabulary of predicates:

**Clinical:**
`TREATS`, `MANAGES`, `CONTRAINDICATED_FOR`, `SIDE_EFFECT`, `DIAGNOSES`, `INDICATES`

**Causal:**
`CAUSES`, `PREVENTS`, `INCREASES_RISK`, `DECREASES_RISK`

**Molecular:**
`BINDS_TO`, `INHIBITS`, `ACTIVATES`, `UPREGULATES`, `DOWNREGULATES`, `ENCODES`, `METABOLIZES`

**Provenance:**
`AUTHORED_BY`, `CITES`, `CITED_BY`, `SUPPORTS`, `CONTRADICTS`, `REFUTES`

## Next Steps

- [Querying](querying.md) - How to query the knowledge graph
- [Storage Options](storage.md) - Database backends
