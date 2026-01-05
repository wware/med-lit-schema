"""
Pytest fixtures for schema tests.

This conftest provides fixtures used by schema-specific tests.
"""

import pytest


@pytest.fixture
def small_entities():
    """Minimal Disease/Gene/Drug-like dicts used to construct pydantic models."""
    return {
        "disease": {
            "entity_id": "C0006142",
            "name": "Breast Cancer",
            "synonyms": ["Breast Carcinoma"],
            "abbreviations": ["BC"],
            "source": "umls",
        },
        "gene": {
            "entity_id": "HGNC:1100",
            "name": "BRCA1",
            "synonyms": ["BRCA1 gene"],
            "abbreviations": ["BRCA1"],
            "source": "hgnc",
        },
        "drug": {
            "entity_id": "RxNorm:1187832",
            "name": "Olaparib",
            "synonyms": ["AZD2281"],
            "abbreviations": ["Ola"],
            "source": "rxnorm",
        },
    }
