"""
Global fixtures for the test suite.

This `conftest.py` file provides fixtures that are available to all tests
in the `tests/` directory and its subdirectories. Fixtures defined here
are used to set up common test data, mock objects, or services that are
required by multiple test modules.

Fixtures:
- `small_entities`: Provides a dictionary of minimal, representative data
  for `Disease`, `Gene`, and `Drug` entities. This is useful for quickly
  instantiating Pydantic models in tests without needing to specify all
  required fields each time.

To use a fixture in a test, simply include its name as an argument in the
test function signature. Pytest will automatically inject the fixture's
return value.

Example:
    def test_something(small_entities):
        disease_data = small_entities["disease"]
        # ... use disease_data to build a Disease model ...

Run all tests with:
    pytest -v

For more information on Pytest fixtures, see:
https://docs.pytest.org/en/stable/how-to/fixtures.html
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