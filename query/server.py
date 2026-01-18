from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
import strawberry
from strawberry.fastapi import GraphQLRouter

from .storage_factory import close_storage, get_engine, get_storage
from .routers import rest_api
from .routers.mcp_api import mcp_server
from .routers import graphiql_custom
from .graphql_schema import Query
from med_lit_schema.storage.interfaces import PipelineStorageInterface



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Initializes storage on startup and closes it on shutdown.
    """
    get_engine()  # Initialize storage
    yield
    close_storage()  # Close storage connections


app = FastAPI(
    title="Medical Literature Knowledge Graph API",
    description="A read-only API for querying the medical literature knowledge graph.",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount REST API
app.include_router(rest_api.router)

# Create a context getter that uses your dependency
async def get_context(
    storage: PipelineStorageInterface = Depends(get_storage),
):
    return {
        "storage": storage,
    }

# Mount GraphQL with context (no built-in GraphiQL)
graphql_schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(
    graphql_schema,
    graphiql=False,  # Disable built-in GraphiQL
    context_getter=get_context,
)

app.include_router(graphql_app, prefix="/graphql")

# Mount custom GraphiQL interface with example queries
app.include_router(graphiql_custom.router, prefix="/graphiql", tags=["GraphQL"])

# Mount MCP API (Server-Sent Events and HTTP endpoints)
app.mount("/mcp/sse", mcp_server.sse_app)
app.mount("/mcp", mcp_server.streamable_http_app)


@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify that the server is running.
    """
    return {"status": "ok"}


# Mount MkDocs static site at /mkdocs if available
# Built during Docker image creation via: mkdocs build
_mkdocs_site = Path(__file__).parent.parent / "site"
if _mkdocs_site.exists():
    app.mount("/mkdocs", StaticFiles(directory=_mkdocs_site, html=True), name="mkdocs")
