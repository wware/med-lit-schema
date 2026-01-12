# API Server Implementation Plan

This document outlines the phased implementation plan for the read-only FastAPI server. The server will expose the medical knowledge graph data via REST, GraphQL, and MCP endpoints, as described in `API_ARCHITECTURE.md`.

## Implementation Status

- ✅ **Phase 1**: Complete (Commit: 1b99df2)
- ✅ **Phase 2**: Complete (Commit: 1b99df2)
- ✅ **Phase 3**: Complete (Commit: c5507b8)
- ✅ **Phase 4**: Complete (Commit: c5507b8)

## Guiding Principles

- **Read-Only**: The API is for querying only. Data ingestion is handled by separate, internal pipelines.
- **Layered Architecture**: The API layer is decoupled from the storage layer via the abstractions in `storage/interfaces.py`.
- **Incremental Implementation**: The plan is broken into phases to build functionality incrementally, ensuring a working product at each stage.
- **Code Reuse**: The API will reuse the existing Pydantic data models (`entity.py`, `relationship.py`) and storage interfaces (`storage/interfaces.py`).

---

## Phase 1: Core Setup & REST API ✅

**Status:** Complete

**Goal:** Establish the basic FastAPI server and expose core data via a simple, versioned RESTful interface.

1.  ✅ **Add Dependencies**:
    - Added `fastapi`, `uvicorn`, and `strawberry-graphql[fastapi]` to project dependencies.

2.  ✅ **Create API Server Entrypoint**:
    - Created `query/server.py` with FastAPI application instance.
    - Added `/health` endpoint.

3.  ✅ **Implement Storage Factory**:
    - Created `query/storage_factory.py` with singleton pattern for `PipelineStorageInterface`.
    - Implemented connection lifecycle management.

4.  ✅ **Implement REST Endpoints**:
    - Created `query/routers/rest_api.py` with REST API router.
    - Implemented all specified endpoints:
        - `GET /api/v1/entities/{entity_id}`
        - `GET /api/v1/entities`
        - `GET /api/v1/relationships`
        - `GET /api/v1/papers/{paper_id}`

---

## Phase 2: GraphQL API ✅

**Status:** Complete (with simplification)

**Goal:** Add a flexible GraphQL query layer for more complex and specific data-fetching needs.

1.  ✅ **Create GraphQL Schema**:
    - Created `query/graphql_schema.py`.
    - Used Strawberry JSON scalar type instead of full Pydantic type conversion to avoid nested type complexity.

2.  ✅ **Implement GraphQL Queries (Resolvers)**:
    - Defined `Query` root type in `query/graphql_schema.py`.
    - Implemented resolvers: `paper(id)`, `entity(id)`, `entities(limit, offset)`, `relationships(...)`.
    - All queries use the storage factory from Phase 1.

3.  ✅ **Mount GraphQL App**:
    - Mounted Strawberry GraphQL application at `/graphql`.
    - GraphiQL interactive playground available at `/graphql/playground`.

**Note:** The GraphQL schema uses JSON scalar types rather than fully-typed Strawberry types due to complexity with nested Pydantic model conversions. This is functional but could be improved for better type safety in the future.

---

## Phase 3: Advanced Functionality (Search & MCP) ✅

**Status:** Complete

**Goal:** Implement semantic search and the Model Context Protocol for AI agent integration.

1.  ✅ **Implement Semantic Search**:
    - Added `POST /api/v1/search/semantic` endpoint to REST API router.
    - Endpoint accepts JSON body with `query_text`, `top_k`, and `threshold` parameters.
    - Implementation:
        1. ✅ Generates embedding using `SentenceTransformerEmbeddingGenerator` from `ingest/`
        2. ✅ Calls `find_similar_relationships` on `RelationshipEmbeddingStorageInterface`
        3. ⚠️  Entity semantic search (`find_by_embedding`) not implemented - only relationship search
        4. ✅ Returns list of similar relationships with similarity scores
    - Added `sentence-transformers` dependency.

2.  ✅ **Integrate MCP (Model Context Protocol)**:
    - Added `mcp` library as dependency (required Python >=3.10).
    - Created `query/routers/mcp_api.py` with FastMCP server.
    - Defined 6 AI-friendly tools:
        - `find_treatments(disease_name, limit)`: Find drugs that treat a disease
        - `find_related_genes(disease_name, limit)`: Find genes associated with a disease
        - `get_entity(entity_id)`: Retrieve entity by canonical ID
        - `search_entities(query, entity_type, limit)`: Search entities by name
        - `get_paper(paper_id)`: Retrieve research paper by ID
    - Exposed MCP endpoints at `/mcp` and `/mcp/sse` (Server-Sent Events).

---

## Phase 4: Containerization & Finalization ✅

**Status:** Complete

**Goal:** Package the API server for easy deployment and orchestration.

1.  ✅ **Create `Dockerfile`**:
    - Created multi-stage `Dockerfile` in project root.
    - Uses `uv` for fast dependency management.
    - Includes health check endpoint.
    - CMD runs `uvicorn main:app --host 0.0.0.0 --port 8000`.

2.  ✅ **Update `docker-compose.yml`**:
    - Added `api` service definition to `docker-compose.yml`.
    - Service depends on postgres with health check condition.
    - Exposed on port 8000 with health checks.
    - Includes volume mount for development.

3.  ✅ **Create `main.py` Entrypoint**:
    - Created `main.py` in project root.
    - Imports and exposes FastAPI `app` instance from `query/server.py`.

---

## Outstanding TODOs

While all phases are functionally complete, the following improvements could be made:

1. **GraphQL Type Safety**: The GraphQL schema currently uses JSON scalar types. For better type safety and schema introspection, implement explicit Strawberry types for all entities and relationships, resolving the nested Pydantic model conversion issues.

2. **Entity Semantic Search**: The semantic search endpoint currently only searches relationships. Implement entity semantic search using a `find_by_embedding` method on the entity storage backend.

3. **Full-Text Search**: Add traditional full-text search endpoints for entity names and paper content (complementing the semantic search).

4. **Test Coverage**: Add comprehensive tests for:
   - REST endpoints (all CRUD operations)
   - GraphQL queries and resolvers
   - Semantic search functionality
   - MCP tools
   - Docker container health

5. **Production Optimizations**:
   - Implement response caching (Redis)
   - Add rate limiting
   - Optimize database queries with indexes
   - Add request logging and metrics
   - Configure CORS appropriately for production

6. **Documentation**:
   - Add API usage examples to README
   - Document MCP tool usage for AI agents
   - Add deployment guide for AWS
