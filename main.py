"""
Entrypoint for the Medical Literature Knowledge Graph API server.

This module imports and exposes the FastAPI application instance for uvicorn.
Run the server with:
    uvicorn main:app --reload
or via docker-compose:
    docker-compose up api
"""

from query.server import app

__all__ = ["app"]
