"""
Storage-agnostic query builder for medical knowledge graph.

Supports PostgreSQL (current) and Neo4j (future) backends.

This module provides a fluent API for building and executing graph queries
against the medical knowledge graph, with support for:
- Entity queries by type and filters
- Relationship queries with confidence thresholds
- Multi-hop graph traversals
- Semantic search using embeddings
- Evidence and provenance filtering

Example:

    # Simple entity query
    query = GraphQuery().entities(entity_type="drug").limit(10)
    results = query.execute()

    # Relationship query with evidence
    query = GraphQuery().relationships(
        predicate="TREATS",
        min_confidence=0.8
    ).with_evidence(study_types=["rct", "meta_analysis"])
    results = query.execute()

    # Multi-hop traversal
    query = GraphQuery().traverse(
        start={"entity_id": "C0006142"},
        path=["TREATS:drug", "TARGETS:protein"]
    )
    results = query.execute()
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

import psycopg2
from psycopg2.extras import RealDictCursor


@dataclass
class QueryResults:
    """
    Results from query execution.

    Attributes:

        results: List of result dictionaries
        count: Number of results returned
        query_time_ms: Query execution time in milliseconds
        query_sql: SQL query that was executed (for debugging)
    """

    results: List[Dict[str, Any]]
    count: int
    query_time_ms: float
    query_sql: Optional[str] = None

    def to_json(self) -> str:
        """
        Convert results to JSON string.

        Returns:

            JSON string representation of results
        """
        return json.dumps({"results": self.results, "count": self.count, "query_time_ms": self.query_time_ms}, default=str)

    def to_dataframe(self):
        """
        Convert results to pandas DataFrame.

        Returns:

            pandas DataFrame with results

        Raises:

            ImportError: If pandas is not installed
        """
        try:
            import pandas as pd

            return pd.DataFrame(self.results)
        except ImportError:
            raise ImportError("pandas is required for to_dataframe(). Install with: pip install pandas")


class GraphQuery:
    """
    Fluent API for building graph queries.

    This class provides a method-chaining interface for constructing queries
    against the medical knowledge graph. Queries are built declaratively and
    executed lazily when .execute() is called.

    Examples:

        # Entity queries
        query = GraphQuery().entities(entity_type="drug").limit(10)

        # Relationship queries
        query = GraphQuery().relationships(
            predicate="TREATS",
            min_confidence=0.8
        ).filter(study_type=["rct", "meta_analysis"])

        # Multi-hop traversal
        query = GraphQuery().traverse(
            start={"entity_id": "C0006142"},
            path=["TREATS:drug", "TARGETS:protein"]
        )

        # Semantic search
        query = GraphQuery().semantic_search("PARP inhibitor", top_k=10)
    """

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize query builder.

        Args:

            connection_string: PostgreSQL connection string. If not provided,
                             uses DATABASE_URL environment variable.
        """
        self.connection_string = connection_string or os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/medlit")
        self._query_type: Optional[str] = None
        self._entity_type: Optional[str] = None
        self._predicate: Optional[str] = None
        self._subject_id: Optional[str] = None
        self._object_id: Optional[str] = None
        self._min_confidence: float = 0.0
        self._filters: Dict[str, Any] = {}
        self._limit: Optional[int] = None
        self._order_by: Optional[tuple] = None
        self._with_evidence: bool = False
        self._study_types: Optional[List[str]] = None
        self._traverse_start: Optional[Dict[str, str]] = None
        self._traverse_path: Optional[List[str]] = None
        self._max_hops: int = 3
        self._semantic_query: Optional[str] = None
        self._semantic_top_k: int = 10
        self._semantic_threshold: float = 0.7

    def entities(self, entity_type: Optional[str] = None, filters: Optional[Dict[str, Any]] = None) -> "GraphQuery":
        """
        Query entities by type and filters.

        Args:

            entity_type: Filter by entity type (drug, disease, gene, etc.)
            filters: Additional filters as key-value pairs

        Returns:

            Self for method chaining

        Example:

            >>> query = GraphQuery().entities(entity_type="drug")
            >>> query = GraphQuery().entities(
            ...     entity_type="drug",
            ...     filters={"fda_approved": True}
            ... )
        """
        self._query_type = "entities"
        self._entity_type = entity_type
        if filters:
            self._filters.update(filters)
        return self

    def relationships(
        self,
        predicate: Optional[str] = None,
        subject_id: Optional[str] = None,
        object_id: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> "GraphQuery":
        """
        Query relationships with optional filters.

        Args:

            predicate: Filter by relationship predicate (TREATS, CAUSES, etc.)
            subject_id: Filter by subject entity ID
            object_id: Filter by object entity ID
            min_confidence: Minimum confidence threshold (0.0 to 1.0)

        Returns:

            Self for method chaining

        Example:

            >>> query = GraphQuery().relationships(predicate="TREATS", min_confidence=0.8)
        """
        self._query_type = "relationships"
        self._predicate = predicate
        self._subject_id = subject_id
        self._object_id = object_id
        self._min_confidence = min_confidence
        return self

    def traverse(self, start: Dict[str, str], path: List[str], max_hops: int = 3) -> "GraphQuery":
        """
        Multi-hop graph traversal.

        Args:

            start: Starting entity as {"entity_id": "ID"} or {"entity_type": "TYPE", "name": "NAME"}
            path: List of relationship patterns like ["TREATS:drug", "TARGETS:protein"]
            max_hops: Maximum number of hops to traverse

        Returns:

            Self for method chaining

        Example:

            >>> query = GraphQuery().traverse(
            ...     start={"entity_id": "C0006142"},
            ...     path=["TREATS:drug", "TARGETS:protein"]
            ... )
        """
        self._query_type = "traverse"
        self._traverse_start = start
        self._traverse_path = path
        self._max_hops = max_hops
        return self

    def semantic_search(
        self,
        query_text: str,
        entity_type: Optional[str] = None,
        top_k: int = 10,
        threshold: float = 0.7,
    ) -> "GraphQuery":
        """
        Semantic search using embeddings.

        Args:

            query_text: Text to search for
            entity_type: Optional filter by entity type
            top_k: Number of results to return
            threshold: Minimum similarity threshold (0.0 to 1.0)

        Returns:

            Self for method chaining

        Example:

            >>> query = GraphQuery().semantic_search("PARP inhibitor", top_k=10)
        """
        self._query_type = "semantic_search"
        self._semantic_query = query_text
        self._entity_type = entity_type
        self._semantic_top_k = top_k
        self._semantic_threshold = threshold
        return self

    def filter(self, **kwargs) -> "GraphQuery":
        """
        Add filters to query.

        Args:

            **kwargs: Filter key-value pairs

        Returns:

            Self for method chaining

        Example:

            >>> query = GraphQuery().entities("drug").filter(fda_approved=True)
        """
        self._filters.update(kwargs)
        return self

    def limit(self, n: int) -> "GraphQuery":
        """
        Limit number of results.

        Args:

            n: Maximum number of results

        Returns:

            Self for method chaining
        """
        self._limit = n
        return self

    def order_by(self, field: str, direction: Literal["asc", "desc"] = "asc") -> "GraphQuery":
        """
        Order results by field.

        Args:

            field: Field name to order by
            direction: Sort direction ("asc" or "desc")

        Returns:

            Self for method chaining
        """
        self._order_by = (field, direction)
        return self

    def with_evidence(self, study_types: Optional[List[str]] = None) -> "GraphQuery":
        """
        Include evidence, optionally filtered by study type.

        Args:

            study_types: Optional list of study types to filter by
                       (e.g., ["rct", "meta_analysis"])

        Returns:

            Self for method chaining
        """
        self._with_evidence = True
        self._study_types = study_types
        return self

    def to_sql(self) -> str:
        """
        Generate PostgreSQL query.

        Returns:

            SQL query string

        Raises:

            ValueError: If query type is not set or invalid
        """
        if self._query_type == "entities":
            return self._build_entity_query()
        elif self._query_type == "relationships":
            return self._build_relationship_query()
        elif self._query_type == "traverse":
            return self._build_traverse_query()
        elif self._query_type == "semantic_search":
            return self._build_semantic_query()
        else:
            raise ValueError(f"Unknown query type: {self._query_type}")

    def _build_entity_query(self) -> str:
        """Build SQL for entity query."""
        # Note: This method builds SQL strings for demonstration.
        # In production, use parameterized queries with cursor.execute(sql, params)
        query = "SELECT * FROM entities"
        conditions = []

        if self._entity_type:
            conditions.append("entity_type = %s")

        # Add property filters
        # Note: Property keys should be validated in production
        for key in self._filters.keys():
            # Basic validation: alphanumeric and underscore only
            if not key.replace("_", "").isalnum():
                raise ValueError(f"Invalid filter key: {key}")
            conditions.append(f"properties->>'{key}' = %s")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        if self._order_by:
            field, direction = self._order_by
            # Validate field name to prevent SQL injection
            allowed_fields = ["id", "name", "entity_type", "confidence", "created_at", "updated_at"]
            if field not in allowed_fields:
                raise ValueError(f"Invalid order field: {field}. Allowed: {allowed_fields}")
            query += f" ORDER BY {field} {direction.upper()}"

        if self._limit:
            query += f" LIMIT {self._limit}"

        # Note: This simplified implementation substitutes parameters for display
        # Real implementation should use cursor.execute(query, params)
        params = []
        if self._entity_type:
            params.append(self._entity_type)
        for value in self._filters.values():
            params.append(str(value))

        # Substitute for demonstration (NOT production code)
        for param in params:
            query = query.replace("%s", f"'{param}'", 1)

        return query

    def _build_relationship_query(self) -> str:
        """Build SQL for relationship query."""
        query = "SELECT r.* FROM relationships r"
        conditions = []
        params = []

        if self._predicate:
            conditions.append("r.predicate = %s")
            params.append(self._predicate)

        if self._subject_id:
            conditions.append("r.subject_id = %s")
            params.append(self._subject_id)

        if self._object_id:
            conditions.append("r.object_id = %s")
            params.append(self._object_id)

        if self._min_confidence > 0:
            conditions.append("r.confidence >= %s")
            params.append(str(self._min_confidence))

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        if self._order_by:
            field, direction = self._order_by
            # Validate field name
            allowed_fields = ["confidence", "created_at", "updated_at", "evidence_count"]
            if field not in allowed_fields:
                raise ValueError(f"Invalid order field: {field}. Allowed: {allowed_fields}")
            query += f" ORDER BY r.{field} {direction.upper()}"

        if self._limit:
            query += f" LIMIT {self._limit}"

        # Substitute parameters for demonstration
        for param in params:
            query = query.replace("%s", f"'{param}'", 1)

        return query

    def _build_traverse_query(self) -> str:
        """Build SQL for multi-hop traversal."""
        # Multi-hop traversal requires recursive CTEs which is a complex feature
        # This is intentionally not implemented in this version
        raise NotImplementedError("Multi-hop traversal queries require recursive CTEs. This feature is planned but not yet implemented. Contributions welcome!")

    def _build_semantic_query(self) -> str:
        """Build SQL for semantic search."""
        # Note: This requires embedding generation which is not implemented here
        query = """
        SELECT e.*,
               1 - (e.embedding <=> %s::vector) AS similarity
        FROM entities e
        WHERE e.embedding IS NOT NULL
        """

        if self._entity_type:
            query += f" AND e.entity_type = '{self._entity_type}'"

        query += f"""
        ORDER BY e.embedding <=> %s::vector
        LIMIT {self._semantic_top_k}
        """

        return query

    def to_cypher(self) -> str:
        """
        Generate Cypher query for Neo4j (future implementation).

        Returns:

            Cypher query string

        Raises:

            NotImplementedError: Neo4j backend not yet implemented
        """
        raise NotImplementedError("Neo4j backend not yet implemented")

    def execute(self) -> QueryResults:
        """
        Execute the query and return results.

        Returns:

            QueryResults object with results and metadata

        Raises:

            ValueError: If query type is not set
            psycopg2.Error: If database connection fails
        """
        import time

        start_time = time.time()

        sql = self.to_sql()

        # Execute query
        conn = psycopg2.connect(self.connection_string)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql)
                results = [dict(row) for row in cursor.fetchall()]

            query_time_ms = (time.time() - start_time) * 1000

            return QueryResults(
                results=results,
                count=len(results),
                query_time_ms=query_time_ms,
                query_sql=sql,
            )
        finally:
            conn.close()


# ============================================================================
# Convenience functions for common queries
# ============================================================================


def find_treatments(
    disease: str,
    min_confidence: float = 0.7,
    study_types: Optional[List[str]] = None,
    connection_string: Optional[str] = None,
) -> QueryResults:
    """
    Find drugs that treat a disease.

    Args:

        disease: Disease name or ID
        min_confidence: Minimum confidence threshold
        study_types: Optional filter by study type (e.g., ["rct", "meta_analysis"])
        connection_string: Optional database connection string

    Returns:

        QueryResults with drug-disease relationships

    Example:

        >>> results = find_treatments("breast cancer", min_confidence=0.8)
    """
    # First, find the disease entity
    disease_query = GraphQuery(connection_string).entities(entity_type="disease").filter(name=disease).limit(1)

    disease_results = disease_query.execute()

    if not disease_results.results:
        return QueryResults(results=[], count=0, query_time_ms=0.0)

    disease_id = disease_results.results[0]["id"]

    # Find relationships where drug treats this disease
    query = GraphQuery(connection_string).relationships(predicate="TREATS", object_id=disease_id, min_confidence=min_confidence)

    if study_types:
        query = query.with_evidence(study_types=study_types)

    return query.execute()


def find_disease_genes(disease: str, min_confidence: float = 0.6, connection_string: Optional[str] = None) -> QueryResults:
    """
    Find genes associated with a disease.

    Args:

        disease: Disease name or ID
        min_confidence: Minimum confidence threshold
        connection_string: Optional database connection string

    Returns:

        QueryResults with gene-disease relationships
    """
    # Find disease entity
    disease_query = GraphQuery(connection_string).entities(entity_type="disease").filter(name=disease).limit(1)

    disease_results = disease_query.execute()

    if not disease_results.results:
        return QueryResults(results=[], count=0, query_time_ms=0.0)

    disease_id = disease_results.results[0]["id"]

    # Find associated genes
    query = GraphQuery(connection_string).relationships(predicate="ASSOCIATED_WITH", object_id=disease_id, min_confidence=min_confidence)

    return query.execute()


def find_drug_mechanisms(drug: str, max_hops: int = 3, connection_string: Optional[str] = None) -> QueryResults:
    """
    Find mechanism of action for a drug.

    Args:

        drug: Drug name or ID
        max_hops: Maximum path length
        connection_string: Optional database connection string

    Returns:

        QueryResults with drug mechanism paths
    """
    # Find drug entity
    drug_query = GraphQuery(connection_string).entities(entity_type="drug").filter(name=drug).limit(1)

    drug_results = drug_query.execute()

    if not drug_results.results:
        return QueryResults(results=[], count=0, query_time_ms=0.0)

    drug_id = drug_results.results[0]["id"]

    # Find mechanism (this would need multi-hop traversal)
    query = GraphQuery(connection_string).traverse(start={"entity_id": drug_id}, path=["TARGETS:protein", "REGULATES:gene"], max_hops=max_hops)

    return query.execute()


def search_by_symptoms(symptoms: List[str], min_match: int = 2, connection_string: Optional[str] = None) -> QueryResults:
    """
    Differential diagnosis by symptoms.

    Args:

        symptoms: List of symptom names
        min_match: Minimum number of symptoms that must match
        connection_string: Optional database connection string

    Returns:

        QueryResults with matching diseases

    Raises:

        NotImplementedError: This feature is not yet implemented
    """
    # This requires complex query logic to find diseases
    # that have at least min_match of the given symptoms
    raise NotImplementedError(
        "Symptom-based differential diagnosis is not yet implemented. This requires joining entities and relationships to find diseases that match multiple symptoms. Contributions welcome!"
    )
