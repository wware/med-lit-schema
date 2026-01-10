"""
Tests for query client library.

Tests the GraphQuery fluent API and query building functionality.

Run with: uv run pytest tests/test_query_client.py -v
"""

import pytest
from unittest.mock import MagicMock, patch

from query.client import GraphQuery, QueryResults, find_treatments


class TestQueryResults:
    """Test QueryResults class."""

    def test_query_results_creation(self):
        """Test creating QueryResults."""
        results = QueryResults(results=[{"id": "1", "name": "Test"}], count=1, query_time_ms=10.5, query_sql="SELECT * FROM test")

        assert results.count == 1
        assert results.query_time_ms == 10.5
        assert len(results.results) == 1

    def test_to_json(self):
        """Test JSON serialization."""
        results = QueryResults(results=[{"id": "1", "name": "Test"}], count=1, query_time_ms=10.5)

        json_str = results.to_json()
        assert "Test" in json_str
        assert "10.5" in json_str

    def test_to_dataframe(self):
        """Test DataFrame conversion."""
        pytest.importorskip("pandas")

        results = QueryResults(results=[{"id": "1", "name": "Test"}], count=1, query_time_ms=10.5)

        df = results.to_dataframe()
        assert len(df) == 1
        assert "id" in df.columns
        assert "name" in df.columns

    def test_to_dataframe_without_pandas(self):
        """Test that to_dataframe raises error without pandas."""
        results = QueryResults(results=[{"id": "1"}], count=1, query_time_ms=10.5)

        with patch.dict("sys.modules", {"pandas": None}):
            with pytest.raises(ImportError):
                results.to_dataframe()


class TestGraphQuery:
    """Test GraphQuery builder."""

    def test_init_with_default_connection(self):
        """Test initialization with default connection string."""
        query = GraphQuery()
        assert query.connection_string is not None

    def test_init_with_custom_connection(self):
        """Test initialization with custom connection string."""
        conn_str = "postgresql://user:pass@host:5432/db"
        query = GraphQuery(connection_string=conn_str)
        assert query.connection_string == conn_str

    def test_entities_query(self):
        """Test entities query builder."""
        query = GraphQuery().entities(entity_type="drug")

        assert query._query_type == "entities"
        assert query._entity_type == "drug"

    def test_entities_with_filters(self):
        """Test entities query with filters."""
        query = GraphQuery().entities(entity_type="drug", filters={"fda_approved": True})

        assert query._entity_type == "drug"
        assert "fda_approved" in query._filters
        assert query._filters["fda_approved"] is True

    def test_relationships_query(self):
        """Test relationships query builder."""
        query = GraphQuery().relationships(predicate="TREATS", min_confidence=0.8)

        assert query._query_type == "relationships"
        assert query._predicate == "TREATS"
        assert query._min_confidence == 0.8

    def test_relationships_with_all_params(self):
        """Test relationships query with all parameters."""
        query = GraphQuery().relationships(predicate="TREATS", subject_id="drug_123", object_id="disease_456", min_confidence=0.9)

        assert query._predicate == "TREATS"
        assert query._subject_id == "drug_123"
        assert query._object_id == "disease_456"
        assert query._min_confidence == 0.9

    def test_traverse_query(self):
        """Test traverse query builder."""
        query = GraphQuery().traverse(start={"entity_id": "drug_123"}, path=["TREATS:disease", "HAS_SYMPTOM:symptom"], max_hops=2)

        assert query._query_type == "traverse"
        assert query._traverse_start == {"entity_id": "drug_123"}
        assert len(query._traverse_path) == 2
        assert query._max_hops == 2

    def test_semantic_search_query(self):
        """Test semantic search query builder."""
        query = GraphQuery().semantic_search("PARP inhibitor", entity_type="drug", top_k=15, threshold=0.8)

        assert query._query_type == "semantic_search"
        assert query._semantic_query == "PARP inhibitor"
        assert query._entity_type == "drug"
        assert query._semantic_top_k == 15
        assert query._semantic_threshold == 0.8

    def test_filter_method(self):
        """Test filter method chaining."""
        query = GraphQuery().entities("drug").filter(fda_approved=True, drug_class="antibiotic")

        assert query._filters["fda_approved"] is True
        assert query._filters["drug_class"] == "antibiotic"

    def test_limit_method(self):
        """Test limit method."""
        query = GraphQuery().entities("drug").limit(50)
        assert query._limit == 50

    def test_order_by_method(self):
        """Test order_by method."""
        query = GraphQuery().entities("drug").order_by("name", "desc")
        assert query._order_by == ("name", "desc")

    def test_with_evidence_method(self):
        """Test with_evidence method."""
        query = GraphQuery().relationships("TREATS").with_evidence(study_types=["rct", "meta_analysis"])

        assert query._with_evidence is True
        assert query._study_types == ["rct", "meta_analysis"]

    def test_method_chaining(self):
        """Test full method chaining."""
        query = GraphQuery().entities(entity_type="drug").filter(fda_approved=True).order_by("name", "asc").limit(100)

        assert query._query_type == "entities"
        assert query._entity_type == "drug"
        assert query._filters["fda_approved"] is True
        assert query._order_by == ("name", "asc")
        assert query._limit == 100

    def test_build_entity_query_simple(self):
        """Test SQL generation for simple entity query."""
        query = GraphQuery().entities(entity_type="drug").limit(10)
        sql = query.to_sql()

        assert "SELECT * FROM entities" in sql
        assert "entity_type = 'drug'" in sql
        assert "LIMIT 10" in sql

    def test_build_entity_query_with_filters(self):
        """Test SQL generation for entity query with filters."""
        query = GraphQuery().entities(entity_type="drug").filter(fda_approved="true").limit(20)

        sql = query.to_sql()
        assert "SELECT * FROM entities" in sql
        assert "entity_type = 'drug'" in sql
        assert "properties->>'fda_approved' = 'true'" in sql
        assert "LIMIT 20" in sql

    def test_build_entity_query_with_order(self):
        """Test SQL generation with ordering."""
        query = GraphQuery().entities(entity_type="drug").order_by("name", "desc")
        sql = query.to_sql()

        assert "ORDER BY name DESC" in sql

    def test_build_relationship_query(self):
        """Test SQL generation for relationship query."""
        query = GraphQuery().relationships(predicate="TREATS", min_confidence=0.8).limit(50)

        sql = query.to_sql()
        assert "SELECT r.* FROM relationships r" in sql
        assert "r.predicate = 'TREATS'" in sql
        assert "r.confidence >= '0.8'" in sql
        assert "LIMIT 50" in sql

    def test_build_relationship_query_with_entities(self):
        """Test SQL generation for relationship query with entity filters."""
        query = GraphQuery().relationships(predicate="TREATS", subject_id="drug_123", object_id="disease_456")

        sql = query.to_sql()
        assert "r.subject_id = 'drug_123'" in sql
        assert "r.object_id = 'disease_456'" in sql

    def test_build_traverse_query(self):
        """Test SQL generation for traverse query (placeholder)."""
        query = GraphQuery().traverse(start={"entity_id": "drug_123"}, path=["TREATS:disease"], max_hops=2)

        # Should raise NotImplementedError
        with pytest.raises(NotImplementedError):
            query.to_sql()

    def test_build_semantic_query(self):
        """Test SQL generation for semantic search."""
        query = GraphQuery().semantic_search("PARP inhibitor", entity_type="drug", top_k=10)

        sql = query.to_sql()
        assert "embedding" in sql
        assert "e.entity_type = 'drug'" in sql
        assert "LIMIT 10" in sql

    def test_to_cypher_not_implemented(self):
        """Test that Cypher generation raises NotImplementedError."""
        query = GraphQuery().entities("drug")

        with pytest.raises(NotImplementedError):
            query.to_cypher()

    def test_to_sql_without_query_type(self):
        """Test that to_sql raises error without query type."""
        query = GraphQuery()

        with pytest.raises(ValueError):
            query.to_sql()

    @patch("psycopg2.connect")
    def test_execute_query(self, mock_connect):
        """Test query execution with mocked database."""
        # Mock database connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"id": "1", "name": "Drug A"}, {"id": "2", "name": "Drug B"}]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Execute query
        query = GraphQuery().entities(entity_type="drug").limit(2)
        results = query.execute()

        # Verify results
        assert results.count == 2
        assert len(results.results) == 2
        assert results.query_time_ms >= 0
        assert results.query_sql is not None

    @patch("psycopg2.connect")
    def test_execute_relationship_query(self, mock_connect):
        """Test relationship query execution."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"subject_id": "drug_1", "object_id": "disease_1", "predicate": "TREATS", "confidence": 0.85}]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        query = GraphQuery().relationships(predicate="TREATS", min_confidence=0.8)
        results = query.execute()

        assert results.count == 1
        assert results.results[0]["predicate"] == "TREATS"


class TestConvenienceFunctions:
    """Test convenience functions."""

    @patch("query.client.GraphQuery.execute")
    def test_find_treatments(self, mock_execute):
        """Test find_treatments convenience function."""
        # Mock disease lookup
        mock_execute.side_effect = [
            # First call: find disease
            QueryResults(results=[{"id": "disease_123", "name": "breast cancer"}], count=1, query_time_ms=5.0),
            # Second call: find treatments
            QueryResults(results=[{"subject_id": "drug_1", "object_id": "disease_123", "confidence": 0.9}], count=1, query_time_ms=10.0),
        ]

        results = find_treatments("breast cancer", min_confidence=0.8)
        assert results.count == 1

    @patch("query.client.GraphQuery.execute")
    def test_find_treatments_no_disease(self, mock_execute):
        """Test find_treatments when disease not found."""
        mock_execute.return_value = QueryResults(results=[], count=0, query_time_ms=5.0)

        results = find_treatments("unknown disease")
        assert results.count == 0


class TestQueryValidation:
    """Test query validation and error handling."""

    def test_entities_requires_valid_type(self):
        """Test that entities accepts any string type."""
        query = GraphQuery().entities(entity_type="custom_type")
        assert query._entity_type == "custom_type"

    def test_confidence_range(self):
        """Test that confidence values are accepted."""
        query = GraphQuery().relationships(min_confidence=0.5)
        assert query._min_confidence == 0.5

        query = GraphQuery().relationships(min_confidence=1.0)
        assert query._min_confidence == 1.0

    def test_limit_positive(self):
        """Test that limit accepts positive values."""
        query = GraphQuery().entities("drug").limit(100)
        assert query._limit == 100

    def test_order_direction_values(self):
        """Test order_by direction values."""
        query = GraphQuery().entities("drug").order_by("name", "asc")
        assert query._order_by[1] == "asc"

        query = GraphQuery().entities("drug").order_by("name", "desc")
        assert query._order_by[1] == "desc"


class TestQueryBuilder:
    """Test complex query building scenarios."""

    def test_multiple_filters(self):
        """Test adding multiple filters."""
        query = GraphQuery().entities("drug").filter(fda_approved="true", drug_class="antibiotic", mechanism="beta-lactam")

        assert len(query._filters) == 3
        assert query._filters["fda_approved"] == "true"
        assert query._filters["drug_class"] == "antibiotic"

    def test_chained_filter_calls(self):
        """Test chaining multiple filter() calls."""
        query = GraphQuery().entities("drug").filter(fda_approved="true").filter(drug_class="antibiotic")

        assert len(query._filters) == 2

    def test_complex_relationship_query(self):
        """Test complex relationship query with all options."""
        query = GraphQuery().relationships(predicate="TREATS", subject_id="drug_123", min_confidence=0.8).with_evidence(study_types=["rct"]).order_by("confidence", "desc").limit(20)

        assert query._query_type == "relationships"
        assert query._predicate == "TREATS"
        assert query._subject_id == "drug_123"
        assert query._min_confidence == 0.8
        assert query._with_evidence is True
        assert query._study_types == ["rct"]
        assert query._order_by == ("confidence", "desc")
        assert query._limit == 20
