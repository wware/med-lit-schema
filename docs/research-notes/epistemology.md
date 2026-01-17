# Epistemology & Design

Deep insights on knowledge graph design from a ChatGPT conversation that shaped the project's architecture.

!!! note "Source"
    This summarizes key insights from `EPISTEMOLOGY_VIBES.md` in the repository root - the full document is worth reading for context.

## The Three-Graph Model

The most important architectural insight: think in **three stacked graphs**, not one.

### 1. Extraction Graph

The raw output of NLP/LLM processing.

- Noisy
- Model-dependent
- Reproducible
- **Disposable**

### 2. Claim Graph

What paper authors claim to be true.

- Paper-level assertions
- Versioned
- Citable
- **Contradictory by nature**

### 3. Evidence Graph

Empirical evidence from experiments.

- Fine-grained
- Multi-modal (text, stats, figures)
- Weighted
- **Reusable across claims**

## Why This Matters

Your system isn't just answering:

> "Is A related to B?"

It's answering:

> "Who claims A is related to B, under what conditions, with what strength, and who disagrees?"

Those are **different objects** that require different treatment.

## Edges vs. Predicates

**Key insight:** Edges are not predicates. Predicates are *meanings*; edges are *events*.

RDF trains us to think `(subject, predicate, object)` is the atomic unit. But that conflates:

1. The **linguistic predicate** ("treats", "causes")
2. The **act of asserting** that predicate
3. The **evidence** supporting the assertion

### Consequences

**Multiple edges can share the same predicate:**

Two papers can both claim "Drug X TREATS Disease Y" but:
- One is an RCT
- One is a case report
- One is later refuted

Those are *different edges*, not different predicates.

**Edges can be versioned, contradicted, deprecated:**

- "This claim edge was superseded"
- "This extraction edge is obsolete"
- "This evidence edge is weak but consistent"

## Query Design Principle

> Queries should target claims, not extractions or evidence by default.

But:
- Claims should *reference* evidence
- Claims should *trace back* to extractions
- Queries should be able to "drop down" a layer when needed

### Example

**Default (clinician):**
> "Find drugs that treat Disease X"
> → returns **claims**

**Advanced (researcher):**
> "Show me the evidence supporting this claim"
> → traverses to **evidence**

**Debug (auditor):**
> "Why does this claim exist?"
> → traverses to **extraction provenance**

## Testing Expressibility

Test **design invariants**, not data correctness.

```python
def test_clinician_question_is_expressible():
    """Can we express: 'Which drugs treat Disease X with high-quality evidence?'"""
    query = build_clinical_query()
    assert query.is_valid()
    assert query.target_layer == Layer.CLAIM

def test_clinical_query_cannot_use_extraction_edges():
    """Clinical queries shouldn't leak low-level artifacts."""
    edges = build_clinical_query_edges()
    assert all(isinstance(e, ClaimEdge) for e in edges)
```

## Edge Type Hierarchy

```python
class Edge(BaseModel):
    """Physical edge - no semantics."""
    id: EdgeId
    subject: EntityRef
    object: EntityRef
    provenance: Provenance

class ExtractionEdge(Edge):
    """What did the model say?"""
    extractor: ModelInfo
    confidence: float

class ClaimEdge(Edge):
    """What does the paper claim?"""
    predicate: ClaimPredicate
    asserted_by: PaperId
    polarity: Polarity  # supports / refutes / neutral

class EvidenceEdge(Edge):
    """What supports or refutes the claim?"""
    evidence_type: EvidenceType
    strength: float
```

## Key Takeaways

1. **Don't prematurely unify** Relationship, Evidence, and Claim
2. **Edges are events**, not just tuples
3. **Layer separation** enables cleaner queries
4. **Test expressibility**, not correctness
5. **Protect conceptual integrity** as the project evolves

## Further Reading

- `EPISTEMOLOGY_VIBES.md` (repository root) - Complete conversation transcript
- [Architecture](../developer-guide/architecture.md) - Domain/persistence separation
