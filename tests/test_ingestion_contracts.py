"""Contract tests for ingestion pipeline stages."""

import json
import pytest
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

# Entity types from base.EntityType enum (serialized as lowercase strings)
EntityType = Literal[
    "disease",
    "symptom",
    "drug",
    "gene",
    "mutation",
    "protein",
    "pathway",
    "anatomical_structure",
    "procedure",
    "test",
    "biomarker",
    "paper",
    "author",
    "institution",
    "clinical_trial",
    "hypothesis",
    "study_design",
    "statistical_method",
]


class EntityContract(BaseModel):
    """Contract for hypothetical entities.jsonl output."""

    entity_id: str
    name: str
    type: EntityType
    synonyms: list[str] = []
    provenance: dict


class EntityReferenceContract(BaseModel):
    """Contract for entity references within edges."""

    id: str
    name: str
    type: EntityType


class ProvenanceContract(BaseModel):
    """Contract for provenance information."""

    source_type: str
    source_id: str
    source_version: str | None = None
    notes: str | None = None


class ExtractorContract(BaseModel):
    """Contract for model/extractor information."""

    name: str
    provider: str
    temperature: float | None = None
    version: str | None = None


class EdgeContract(BaseModel):
    """Contract for extraction_edges.jsonl output (Stage 1: NER Pipeline)."""

    id: str
    subject: EntityReferenceContract
    object: EntityReferenceContract
    provenance: ProvenanceContract
    extractor: ExtractorContract
    confidence: float


# =============================================================================
# Edge Contract Tests (extraction_edges.jsonl from ner_pipeline.py)
# =============================================================================


def test_extraction_edges_output_format():
    """Test that extraction_edges.jsonl conforms to EdgeContract."""
    output_file = Path("output/extraction_edges.jsonl")

    if not output_file.exists():
        pytest.skip("No extraction_edges.jsonl found (run: uv run python ingest/ner_pipeline.py)")

    # Skip if file is empty (no data to validate)
    if output_file.stat().st_size == 0:
        pytest.skip("extraction_edges.jsonl is empty (run: uv run python ingest/ner_pipeline.py)")

    edge_ids = set()
    line_count = 0

    with open(output_file) as f:
        for line_num, line in enumerate(f, 1):
            line_count += 1

            # Test 1: Valid JSON
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                pytest.fail(f"Line {line_num}: Invalid JSON: {e}")

            # Test 2: Conforms to contract
            try:
                edge = EdgeContract(**data)
            except ValidationError as e:
                pytest.fail(f"Line {line_num}: Contract violation: {e}")

            # Test 3: No duplicate IDs
            if edge.id in edge_ids:
                pytest.fail(f"Line {line_num}: Duplicate edge id: {edge.id}")
            edge_ids.add(edge.id)

            # Test 4: Confidence in valid range
            if not 0.0 <= edge.confidence <= 1.0:
                pytest.fail(f"Line {line_num}: Confidence {edge.confidence} out of range [0, 1]")

    # Test 5: Non-empty output (should not reach here if file was empty due to skip above)
    assert line_count > 0, "extraction_edges.jsonl is empty"

    print(f"Edge contract validated: {line_count} edges")


def test_extraction_edges_provenance():
    """Test that edge provenance is complete and traceable."""
    output_file = Path("output/extraction_edges.jsonl")

    if not output_file.exists():
        pytest.skip("No extraction_edges.jsonl found")

    with open(output_file) as f:
        for line_num, line in enumerate(f, 1):
            data = json.loads(line)
            prov = data.get("provenance", {})

            # source_type should indicate origin
            assert prov.get("source_type"), f"Line {line_num}: Missing source_type"

            # source_id should reference the paper
            assert prov.get("source_id"), f"Line {line_num}: Missing source_id"

            # Extractor info must be present
            extractor = data.get("extractor", {})
            assert extractor.get("name"), f"Line {line_num}: Missing extractor name"
            assert extractor.get("provider"), f"Line {line_num}: Missing extractor provider"


def test_extraction_edges_entity_references():
    """Test that entity references in edges are well-formed."""
    output_file = Path("output/extraction_edges.jsonl")

    if not output_file.exists():
        pytest.skip("No extraction_edges.jsonl found")

    with open(output_file) as f:
        for line_num, line in enumerate(f, 1):
            data = json.loads(line)

            for role in ("subject", "object"):
                ref = data.get(role, {})

                # ID should follow canonical format (TYPE:identifier)
                entity_id = ref.get("id", "")
                assert ":" in entity_id, f"Line {line_num}: {role} id '{entity_id}' missing type prefix"

                # Name should be non-empty
                assert ref.get("name"), f"Line {line_num}: {role} missing name"

                # Type should be present
                assert ref.get("type"), f"Line {line_num}: {role} missing type"


# =============================================================================
# Entity Contract Tests (entities.jsonl - hypothetical future output)
# =============================================================================


def test_stage1_output_format():
    """Test that Stage 1 output conforms to contract."""
    output_file = Path("output/entities.jsonl")

    if not output_file.exists():
        pytest.skip("No Stage 1 output file found")

    entity_ids = set()
    line_count = 0

    with open(output_file) as f:
        for line_num, line in enumerate(f, 1):
            line_count += 1

            # Test 1: Valid JSON
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                pytest.fail(f"Line {line_num}: Invalid JSON: {e}")

            # Test 2: Conforms to contract
            try:
                entity = EntityContract(**data)
            except ValidationError as e:
                pytest.fail(f"Line {line_num}: Contract violation: {e}")

            # Test 3: No duplicate IDs
            if entity.entity_id in entity_ids:
                pytest.fail(f"Line {line_num}: Duplicate entity_id: {entity.entity_id}")
            entity_ids.add(entity.entity_id)

    # Test 4: Non-empty output
    assert line_count > 0, "Stage 1 produced empty output"

    print(f"Stage 1 contract validated: {line_count} entities")


def test_stage1_provenance_completeness():
    """Test that provenance is complete and traceable."""
    output_file = Path("output/entities.jsonl")

    if not output_file.exists():
        pytest.skip("No Stage 1 output file found")

    with open(output_file) as f:
        for line_num, line in enumerate(f, 1):
            data = json.loads(line)
            prov = data.get("provenance", {})

            # Required provenance fields
            assert "pipeline_info" in prov, f"Line {line_num}: Missing pipeline_info"
            assert "model_info" in prov, f"Line {line_num}: Missing model_info"
            assert "execution_info" in prov, f"Line {line_num}: Missing execution_info"

            # Pipeline info must have name and version
            assert prov["pipeline_info"].get("name"), f"Line {line_num}: Missing pipeline name"
            assert prov["pipeline_info"].get("version"), f"Line {line_num}: Missing pipeline version"

            # Model info must specify model and provider
            assert prov["model_info"].get("name"), f"Line {line_num}: Missing model name"
            assert prov["model_info"].get("provider"), f"Line {line_num}: Missing model provider"
