# pmc_ner_pipeline.py
"""
Stage 1: Entity Extraction Pipeline

Extracts biomedical entities from PMC XML files using BioBERT NER model.
Uses proper schema from base.py, entity.py, and relationship.py with Pydantic validation.
Stores canonical entities in SQLite with alias mappings for entity resolution.
Outputs ExtractionEdge objects for knowledge graph construction.

Usage:
    docker-compose run pipeline

Output:
    - entities.db: SQLite database with canonical entities and aliases
    - extraction_edges.jsonl: ExtractionEdge objects with full provenance
    - nodes.csv: Extracted nodes for debugging/inspection (legacy)
    - edges.csv: Co-occurrence edges for debugging/inspection (legacy)
"""

from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
import pandas as pd
from lxml import etree
from pathlib import Path
import sqlite3
from datetime import datetime
import os
import json
import socket
import platform
import subprocess
import uuid

# Import proper schema
from base import (
    EntityType, EntityReference, ModelInfo,
    ExtractionEdge, Provenance
)
from entity import (
    Disease,
    ExtractionProvenance, ExtractionPipelineInfo,
    PromptInfo, ExecutionInfo, EntityResolutionInfo
)

# ------------------------------
# Create extraction provenance metadata
# ------------------------------
def get_git_info():
    """Get git information for provenance tracking."""
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL).decode().strip()
        commit_short = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], stderr=subprocess.DEVNULL).decode().strip()
        branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], stderr=subprocess.DEVNULL).decode().strip()
        dirty = subprocess.call(['git', 'diff', '--quiet']) != 0
        return commit, commit_short, branch, dirty
    except Exception:
        return "unknown", "unknown", "unknown", False

git_commit, git_commit_short, git_branch, git_dirty = get_git_info()

# Pipeline info for provenance
pipeline_info = ExtractionPipelineInfo(
    name="pmc_ner_pipeline",
    version="1.0.0",
    git_commit=git_commit,
    git_commit_short=git_commit_short,
    git_branch=git_branch,
    git_dirty=git_dirty,
    repo_url="https://github.com/wware/med-lit-graph"
)

# Model info for provenance
model_name = "ugaray96/biobert_ncbi_disease_ner"
model_info = ModelInfo(
    name=model_name,
    provider="huggingface",
    temperature=None,  # NER models don't use temperature
    version=None
)

# Prompt info (NER doesn't use prompts, but we track the model configuration)
prompt_info = PromptInfo(
    version="v1",
    template="ner_biobert_ncbi_disease",
    checksum=None
)

# Execution info
execution_start = datetime.now()
execution_info = ExecutionInfo(
    timestamp=execution_start.isoformat(),
    hostname=socket.gethostname(),
    python_version=platform.python_version(),
    duration_seconds=None  # Will be updated at end
)

# ------------------------------
# Setup NER pipeline
# ------------------------------
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForTokenClassification.from_pretrained(model_name)
ner_pipeline = pipeline(
    "ner",
    model=model,
    tokenizer=tokenizer,
    aggregation_strategy="simple"  # Groups subwords into entities
)

# ------------------------------
# Setup SQLite canonical entity DB
# ------------------------------
os.makedirs("/app/output", exist_ok=True)
db_path = "/app/output/entities.db"
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA foreign_keys = ON;")

# Create tables - now stores serialized Pydantic models
conn.execute("""
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT UNIQUE,
    canonical_name TEXT,
    type TEXT,
    entity_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);
""")
conn.execute("""
CREATE TABLE IF NOT EXISTS aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    name TEXT UNIQUE,
    source TEXT,
    confidence REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
""")
conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_id ON entities(entity_id);")
conn.execute("CREATE INDEX IF NOT EXISTS idx_alias_name ON aliases(name);")
conn.commit()

# ------------------------------
# Helper functions for SQLite serialization
# ------------------------------
def serialize_entity_to_sqlite(entity: Disease) -> dict:
    """
    Serialize a Pydantic Disease model to SQLite-compatible dict.

    Stores the full model as JSON for complete reconstruction,
    plus key fields for efficient querying.
    """
    return {
        'entity_id': entity.entity_id,
        'canonical_name': entity.name,
        'type': entity.entity_type,
        'entity_json': entity.model_dump_json()
    }

def deserialize_entity_from_sqlite(row: tuple) -> Disease:
    """
    Deserialize a Disease entity from SQLite row.

    Args:
        row: (id, entity_id, canonical_name, type, entity_json, created_at, updated_at)
    """
    entity_json = row[4]  # entity_json column
    return Disease.model_validate_json(entity_json)

# Stopwords to filter out common non-entity words
STOPWORDS = {
    "acquired", "human", "chronic", "enter", "lymph",
    "the", "and", "or", "but", "with", "from", "that",
    "this", "these", "those", "their", "there"
}

# Track entities created in this run for entity resolution stats
entities_created_count = 0
entities_matched_count = 0

def get_or_create_entity(name: str, entity_type: str = "Disease", source: str = None, confidence: float = None) -> tuple[str, int]:
    """
    Get existing entity or create new canonical Disease entity with alias.

    Uses proper Pydantic Disease model with validation and stores as JSON in SQLite.
    Returns both the canonical_entity_id (for graph edges) and db_row_id (for alias FK).

    Args:
        name: Entity name as extracted from text
        entity_type: Entity type (currently only Disease supported by NER model)
        source: PMC ID where entity was found
        confidence: NER confidence score

    Returns:
        tuple: (canonical_entity_id str for use in graph, db_row_id int for SQLite FK)

    This enables entity resolution: multiple mentions of the same entity
    (e.g., "HIV", "HTLV-III", "LAV") can be mapped to the same canonical ID.
    Currently does simple name matching; Stage 3 will add embedding-based clustering.
    """
    global entities_created_count, entities_matched_count

    # Check if alias exists
    cursor = conn.execute("SELECT entity_id FROM aliases WHERE name=?", (name,))
    row = cursor.fetchone()
    if row:
        entities_matched_count += 1
        db_row_id = row[0]
        # Get the canonical entity_id from entities table
        cursor = conn.execute("SELECT entity_id FROM entities WHERE id=?", (db_row_id,))
        canonical_entity_id = cursor.fetchone()[0]
        return canonical_entity_id, db_row_id

    # Create new Disease entity using proper schema
    canonical_entity_id = f"DISEASE:{name.lower().replace(' ', '_')}"
    disease = Disease(
        entity_id=canonical_entity_id,
        name=name,
        synonyms=[],
        abbreviations=[],
        source="extracted"
    )

    # Serialize to SQLite
    entity_dict = serialize_entity_to_sqlite(disease)

    # Insert new entity
    cursor = conn.execute(
        """INSERT OR IGNORE INTO entities (entity_id, canonical_name, type, entity_json)
           VALUES (?, ?, ?, ?)""",
        (entity_dict['entity_id'], entity_dict['canonical_name'],
         entity_dict['type'], entity_dict['entity_json'])
    )
    db_row_id = cursor.lastrowid
    if db_row_id == 0:
        # Entity already exists (race condition or duplicate)
        cursor = conn.execute("SELECT id, entity_id FROM entities WHERE entity_id=?", (canonical_entity_id,))
        row = cursor.fetchone()
        db_row_id = row[0]
        canonical_entity_id = row[1]
        entities_matched_count += 1
    else:
        entities_created_count += 1

    # Insert alias
    conn.execute(
        "INSERT OR IGNORE INTO aliases (entity_id, name, source, confidence) VALUES (?, ?, ?, ?)",
        (db_row_id, name, source, confidence)
    )
    conn.commit()
    return canonical_entity_id, db_row_id

# ------------------------------
# Process PMC XMLs
# ------------------------------
input_dir = Path("./pmc_xmls")
nodes = []
extraction_edges = []  # List of ExtractionEdge objects
edges_dict = {}  # {(subject_id, object_id): count} for legacy CSV
processed_count = 0

for xml_file in input_dir.glob("PMC*.xml"):
    pmc_id = xml_file.stem
    tree = etree.parse(str(xml_file))
    root = tree.getroot()

    # Extract text - prefer abstract, fall back to body
    text_chunks = [p.text for p in root.findall(".//abstract//p") if p.text]
    if not text_chunks:
        text_chunks = [p.text for p in root.findall(".//body//p") if p.text]
    if not text_chunks:
        continue
    full_text = " ".join(text_chunks)

    # Run NER
    entities = ner_pipeline(full_text)
    entity_refs_in_text = []  # List of EntityReference objects

    for ent in entities:
        # Filter by entity label - this model uses 'Disease' and 'No Disease'
        label = ent.get("entity_group", ent.get("entity", "O"))
        if label != "Disease":
            continue

        name = ent["word"].strip()

        # Skip obvious garbage
        if len(name) < 3:  # Minimum 3 characters
            continue
        if name in ["(", ")", ",", ".", "-"]:
            continue
        if name.startswith("##"):  # Subword tokens
            continue
        if name.lower() in STOPWORDS:  # Common non-entity words
            continue

        confidence = ent.get("score", None)

        # Skip low-confidence predictions to reduce noise
        if confidence and confidence < 0.85:
            continue

        # Get or create canonical entity (returns canonical_entity_id str and db_row_id int)
        canonical_entity_id, db_row_id = get_or_create_entity(
            name=name,
            entity_type=label,
            source=pmc_id,
            confidence=confidence
        )

        # Create EntityReference for this mention
        entity_ref = EntityReference(
            id=canonical_entity_id,
            name=name,  # Name as it appeared in text
            type=EntityType.DISEASE
        )
        entity_refs_in_text.append(entity_ref)

        # Store node for legacy CSV output
        nodes.append({
            "id": canonical_entity_id,
            "name": name,
            "type": label,
            "source": pmc_id,
            "confidence": confidence
        })

    # Build ExtractionEdge objects for co-occurrences
    # This is EXTRACTION layer - these are raw model outputs, not semantic claims
    for i in range(len(entity_refs_in_text)):
        for j in range(i + 1, len(entity_refs_in_text)):
            subject_ref = entity_refs_in_text[i]
            object_ref = entity_refs_in_text[j]

            # Create provenance for this edge
            edge_provenance = Provenance(
                source=pmc_id,
                timestamp=datetime.now().isoformat(),
                metadata={
                    "extraction_pipeline": pipeline_info.name,
                    "git_commit": git_commit_short,
                    "model": model_name
                }
            )

            # Create ExtractionEdge with full provenance
            edge = ExtractionEdge(
                id=uuid.uuid4(),
                subject=subject_ref,
                object=object_ref,
                provenance=edge_provenance,
                extractor=model_info,
                confidence=min(
                    float(entities[i].get("score", 0.5)),
                    float(entities[j].get("score", 0.5))
                )  # Use minimum confidence of the two entities
            )
            extraction_edges.append(edge)

            # Also track for legacy CSV
            key = tuple(sorted((subject_ref.id, object_ref.id)))
            edges_dict[key] = edges_dict.get(key, 0) + 1

    processed_count += 1

# ------------------------------
# Finalize provenance and write outputs
# ------------------------------
execution_end = datetime.now()
execution_duration = (execution_end - execution_start).total_seconds()
execution_info.duration_seconds = execution_duration

# Create entity resolution info
entity_resolution_info = EntityResolutionInfo(
    canonical_entities_matched=entities_matched_count,
    new_entities_created=entities_created_count,
    similarity_threshold=0.0,  # Not using similarity matching yet
    embedding_model="none"  # Not using embeddings yet
)

# Create complete extraction provenance
extraction_provenance = ExtractionProvenance(
    extraction_pipeline=pipeline_info,
    models={"ner": model_info},
    prompt=prompt_info,
    execution=execution_info,
    entity_resolution=entity_resolution_info
)

# Write ExtractionEdge objects to JSONL
with open("/app/output/extraction_edges.jsonl", "w") as f:
    for edge in extraction_edges:
        # Serialize to JSON
        edge_dict = edge.model_dump()
        # Convert UUIDs to strings for JSON serialization
        edge_dict['id'] = str(edge_dict['id'])
        f.write(json.dumps(edge_dict) + "\n")

# Write extraction provenance
with open("/app/output/extraction_provenance.json", "w") as f:
    f.write(extraction_provenance.model_dump_json(indent=2))

# Convert nodes and edges to DataFrames for legacy CSV output
nodes_df = pd.DataFrame(nodes).drop_duplicates(subset=["id"])
edges_df = pd.DataFrame([
    {"subject_id": k[0], "object_id": k[1], "relation": "co_occurrence", "weight": v}
    for k, v in edges_dict.items()
])

# Write legacy CSVs for inspection/debugging
nodes_df.to_csv("/app/output/nodes.csv", index=False)
edges_df.to_csv("/app/output/edges.csv", index=False)

print(f"\n{'='*60}")
print("Extraction Complete")
print(f"{'='*60}")
print(f"Processed: {processed_count} XML files")
print(f"Entities: {len(nodes_df)} total mentions")
print(f"  - New canonical entities: {entities_created_count}")
print(f"  - Matched to existing: {entities_matched_count}")
print(f"ExtractionEdges: {len(extraction_edges)}")
print(f"Legacy CSV edges: {len(edges_df)}")
print(f"Duration: {execution_duration:.2f} seconds")
print("\nOutputs:")
print("  - entities.db (SQLite with Pydantic models)")
print("  - extraction_edges.jsonl (ExtractionEdge objects)")
print("  - extraction_provenance.json (full provenance)")
print("  - nodes.csv, edges.csv (legacy format)")
print(f"{'='*60}\n")

# Close database connection
conn.close()
