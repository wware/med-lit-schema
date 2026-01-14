# Neo4j Compatibility

> **Note**: This document describes the theoretical Neo4j compatibility of the storage interfaces. **Neo4j is not currently implemented or planned for this project.** The production system uses PostgreSQL with pgvector for all storage needs. This document is preserved for architectural reference only.

## 1. Introduction

The ingest storage interfaces are designed to be **storage-agnostic**, enabling the medical literature knowledge graph to be backed by various persistence technologies. While the current implementations target SQLite (for testing) and PostgreSQL with pgvector (for production), the abstract interface design is perfectly suited for graph database backends like **Neo4j**.

The interfaces define operations in terms of entities and relationships rather than tables and SQL, making them naturally compatible with graph database concepts. This document explains how the storage interfaces align with Neo4j's graph model and how a Neo4j backend could be implemented.

## 2. Current Interface Design

The ingest process uses several abstract interfaces defined in `storage_interfaces.py`:

### PaperStorageInterface
Stores paper metadata and document structure from medical literature sources (PMC XML files).

**Key methods:**
- `add_paper(paper)` - Store or update a paper
- `get_paper(paper_id)` - Retrieve a paper by ID
- `list_papers(limit, offset)` - List papers with pagination
- `paper_count` - Count total papers

### RelationshipStorageInterface
Stores semantic relationships between biomedical entities as subject-predicate-object triples.

**Key methods:**
- `add_relationship(relationship)` - Store or update a relationship
- `get_relationship(subject_id, predicate, object_id)` - Get a specific triple
- `find_relationships(subject_id, predicate, object_id)` - Query relationships with optional filters
- `relationship_count` - Count total relationships

### EvidenceStorageInterface
Stores evidence items (quantitative metrics, sample sizes, p-values) that support relationships and link them to source papers.

**Key methods:**
- `add_evidence(evidence)` - Store or update evidence
- `get_evidence_by_paper(paper_id)` - Get all evidence from a paper
- `get_evidence_for_relationship(subject_id, predicate, object_id)` - Get evidence supporting a relationship
- `evidence_count` - Count total evidence items

### EntityCollectionInterface
Stores biomedical entities (diseases, genes, drugs, proteins, etc.) with their metadata and embeddings for similarity search.

**Key methods:**
- `add_disease(entity)`, `add_gene(entity)`, `add_drug(entity)` - Store typed entities
- `get_by_id(entity_id)` - Retrieve an entity by ID
- `find_by_name(name, entity_type)` - Search entities by name
- `find_by_embedding(embedding, entity_type, limit)` - Vector similarity search
- `entity_count` - Count total entities

### PipelineStorageInterface
Combines all of the above interfaces into a unified storage abstraction that ingest stages use.

**Properties:**
- `entities` - Access to EntityCollectionInterface
- `papers` - Access to PaperStorageInterface
- `relationships` - Access to RelationshipStorageInterface
- `evidence` - Access to EvidenceStorageInterface
- `relationship_embeddings` - Access to relationship embedding storage
- `close()` - Clean up connections

## 3. Neo4j Compatibility

These interfaces map naturally to Neo4j's graph model for several key reasons:

### Relationship-centric design

The `RelationshipStorageInterface` is designed around triple operations that align perfectly with Neo4j's property graph model:

- **Triple lookup**: `get_relationship(subject_id, predicate, object_id)` maps directly to Cypher pattern matching
- **Pattern queries**: `find_relationships(subject_id, predicate, object_id)` with optional filters is exactly what Neo4j excels at

**Example Cypher for `get_relationship()`:**
```cypher
MATCH (s)-[r:PREDICATE]->(o)
WHERE s.entity_id = $subject_id AND o.entity_id = $object_id
RETURN r
```

This query finds a relationship edge by matching the subject and object nodes and the predicate edge type.

### Graph traversal ready

The `find_relationships()` method with optional filters is designed for graph queries:

- **Find all outgoing relationships from an entity**:
  ```python
  storage.relationships.find_relationships(subject_id="C0006142")
  ```

- **Corresponding Cypher**:
  ```cypher
  MATCH (s {entity_id: "C0006142"})-[r]->(o) RETURN r, o
  ```

- **Find specific predicate relationships**:
  ```python
  storage.relationships.find_relationships(predicate="TREATS")
  ```

- **Corresponding Cypher**:
  ```cypher
  MATCH (s)-[r:TREATS]->(o) RETURN r, s, o
  ```

This design enables multi-hop traversals, pattern matching, and graph algorithms without changing the interface.

### No SQL-specific assumptions

The interfaces are purely about **semantic operations** on graph data:

- **Adding/getting entities and relationships** - No mention of tables, columns, or schemas
- **Finding by criteria** - No SQL WHERE clauses, JOINs, or complex queries
- **Counting** - Simple aggregate operations

**What the interfaces DON'T assume:**
- No table schemas or normalization requirements
- No SQL-specific query operations
- No assumptions about indexing strategies
- No foreign key constraints or referential integrity patterns

This makes implementing a Neo4j backend straightforward - you map each operation to its natural graph equivalent rather than forcing graph operations into a relational model.

## 4. Implementation Example

Here's a conceptual example of how to implement a Neo4j backend:

```python
from neo4j import GraphDatabase
from med_lit_schema.storage.interfaces import PipelineStorageInterface
from med_lit_schema.entity import EntityCollectionInterface
from typing import Optional

class Neo4jPipelineStorage(PipelineStorageInterface):
    """Neo4j implementation of ingest storage."""

    def __init__(self, uri: str, user: str, password: str):
        """Initialize Neo4j connection.

        Args:
            uri: Neo4j connection URI (e.g., "bolt://localhost:7687")
            user: Database username
            password: Database password
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

        # Initialize sub-interfaces
        self._entities = Neo4jEntityCollection(self.driver)
        self._relationships = Neo4jRelationshipStorage(self.driver)
        self._papers = Neo4jPaperStorage(self.driver)
        self._evidence = Neo4jEvidenceStorage(self.driver)
        self._relationship_embeddings = Neo4jRelationshipEmbeddingStorage(self.driver)

    @property
    def entities(self) -> EntityCollectionInterface:
        return self._entities

    @property
    def relationships(self) -> RelationshipStorageInterface:
        return self._relationships

    @property
    def papers(self) -> PaperStorageInterface:
        return self._papers

    @property
    def evidence(self) -> EvidenceStorageInterface:
        return self._evidence

    @property
    def relationship_embeddings(self):
        return self._relationship_embeddings

    def close(self) -> None:
        """Close Neo4j driver connection."""
        self.driver.close()


class Neo4jRelationshipStorage(RelationshipStorageInterface):
    """Neo4j implementation of relationship storage."""

    def __init__(self, driver):
        self.driver = driver

    def add_relationship(self, relationship: "BaseRelationship") -> None:
        """Add or update a relationship as a Neo4j edge."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (s:Entity {entity_id: $subject_id})
                MERGE (o:Entity {entity_id: $object_id})
                MERGE (s)-[r:RELATIONSHIP {predicate: $predicate}]->(o)
                SET r.confidence = $confidence,
                    r.source = $source,
                    r.metadata = $metadata
                """,
                subject_id=relationship.subject_id,
                object_id=relationship.object_id,
                predicate=relationship.predicate,
                confidence=relationship.confidence,
                source=relationship.source,
                metadata=relationship.model_dump_json()
            )

    def get_relationship(
        self, subject_id: str, predicate: str, object_id: str
    ) -> Optional["BaseRelationship"]:
        """Get a specific relationship by triple."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s {entity_id: $subject_id})-[r:RELATIONSHIP {predicate: $predicate}]->(o {entity_id: $object_id})
                RETURN r
                """,
                subject_id=subject_id,
                predicate=predicate,
                object_id=object_id
            )
            record = result.single()
            if record:
                # Convert Neo4j relationship to domain model
                return self._parse_relationship(record["r"])
            return None

    def find_relationships(
        self,
        subject_id: Optional[str] = None,
        predicate: Optional[str] = None,
        object_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list["BaseRelationship"]:
        """Find relationships matching criteria."""
        # Build Cypher query dynamically based on filters
        conditions = []
        params = {}

        if subject_id:
            conditions.append("s.entity_id = $subject_id")
            params["subject_id"] = subject_id
        if predicate:
            conditions.append("r.predicate = $predicate")
            params["predicate"] = predicate
        if object_id:
            conditions.append("o.entity_id = $object_id")
            params["object_id"] = object_id

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        limit_clause = f"LIMIT {limit}" if limit else ""

        query = f"""
        MATCH (s)-[r:RELATIONSHIP]->(o)
        {where_clause}
        RETURN r
        {limit_clause}
        """

        with self.driver.session() as session:
            result = session.run(query, **params)
            return [self._parse_relationship(record["r"]) for record in result]

    @property
    def relationship_count(self) -> int:
        """Count total relationships."""
        with self.driver.session() as session:
            result = session.run("MATCH ()-[r:RELATIONSHIP]->() RETURN count(r) as count")
            return result.single()["count"]

    def _parse_relationship(self, neo4j_rel):
        """Convert Neo4j relationship to domain model."""
        # Implementation would parse the relationship data
        # and reconstruct the appropriate BaseRelationship subclass
        pass
```

## 5. Advantages with Neo4j

Using Neo4j through these interfaces provides several advantages:

### 1. Native graph queries
Neo4j's Cypher query language enables sophisticated graph operations that go beyond the interface methods:
- **Multi-hop traversals**: "Find all drugs that treat diseases related to genes affected by protein X"
- **Shortest path algorithms**: Find the shortest connection between two entities
- **Pattern matching**: Complex graph patterns like "diseases treated by drugs that share a mechanism"
- **Community detection**: Identify clusters of related entities

### 2. Better relationship queries
Neo4j is optimized for relationship traversals, making `find_relationships()` operations extremely fast:
- Index-free adjacency means traversing relationships is O(1)
- No expensive JOINs required to find connected entities
- Query performance scales with the portion of graph accessed, not total size

### 3. Visual exploration
Neo4j Browser provides interactive visualization of the knowledge graph:
- Explore entity connections visually
- Debug relationship extraction quality
- Discover unexpected patterns in the literature
- Share visual representations with researchers

### 4. Cypher power
Complex analytical queries become straightforward:

**Example: Find drugs treating breast cancer with strong evidence**
```cypher
MATCH (drug:Entity {entity_type: 'DRUG'})-[treats:RELATIONSHIP {predicate: 'TREATS'}]->(disease:Entity {entity_id: 'C0006142'})
MATCH (paper:Paper)-[evidence:SUPPORTS]->(treats)
WHERE evidence.confidence > 0.8 AND evidence.sample_size > 100
RETURN drug.name,
       COUNT(paper) as paper_count,
       AVG(evidence.confidence) as avg_confidence
ORDER BY paper_count DESC
```

**Example: Find genes connected to a disease through multiple relationship types**
```cypher
MATCH path = (gene:Entity {entity_type: 'GENE'})-[*1..3]-(disease:Entity {entity_id: 'C0006142'})
RETURN gene.name,
       [rel in relationships(path) | rel.predicate] as connection_types,
       length(path) as distance
ORDER BY distance
```

### 5. Performance
Graph databases are optimized for relationship-heavy workloads:
- Constant-time relationship lookups regardless of database size
- Efficient storage of highly connected data (medical knowledge graphs are highly connected)
- Native support for graph algorithms (PageRank, centrality measures, etc.)
- Horizontal scaling for read-heavy workloads

## 6. Current Implementation Note

The codebase currently provides two storage implementations:

### SQLitePipelineStorage (`storage/backends/sqlite.py`)
- **Purpose**: Testing, development, small datasets
- **Features**: Optional sqlite-vec for vector embeddings, in-memory support
- **Tradeoffs**: Slower for complex relationship queries, limited by SQL JOIN performance

### PostgresPipelineStorage (`storage/backends/postgres.py`)
- **Purpose**: Production deployment with PostgreSQL+pgvector
- **Features**: pgvector extension for embedding similarity search, robust relational model
- **Tradeoffs**: Relationship traversals require JOINs, harder to visualize graph structure

### Design Philosophy

The interface design is **intentionally abstract** to support backend swapping:

- The docstring in `storage_interfaces.py` mentions "PostgreSQL+pgvector for production," but this is just the current production choice
- The interfaces themselves make no assumptions about the backend technology
- A Neo4j backend could be:
  - **Used alongside PostgreSQL** - Neo4j for graph queries, PostgreSQL for vector search
  - **Used instead of PostgreSQL** - Neo4j with vector plugins for all-in-one graph+vector storage
  - **Used as a read replica** - ETL from PostgreSQL to Neo4j for analytical queries

The clean abstraction means you can choose the right tool for each deployment scenario without changing ingest code.

## 7. Conclusion

The ingest storage interfaces are **fully compatible with Neo4j** and graph database implementations. The design is:

- **Graph-native**: Thinks in terms of entities and relationships rather than tables and rows
- **Traversal-friendly**: Methods like `find_relationships()` map directly to graph queries
- **Backend-agnostic**: No SQL-specific assumptions limit implementation choices
- **Clean abstractions**: Pipeline stages work with any conforming implementation

Implementing a Neo4j backend would be straightforward and would unlock powerful graph capabilities:
- Native support for multi-hop traversals and pattern matching
- Superior performance for relationship-heavy queries
- Visual exploration of the medical knowledge graph
- Access to Cypher's expressive query language and graph algorithms

The abstraction is clean, well-designed, and ready for a Neo4j implementation whenever graph database capabilities are needed for the medical literature knowledge graph.
