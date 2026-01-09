"""
SQLModel persistence models for database storage.

This package contains the database schema definitions using SQLModel,
which map domain objects to database tables.

Available Models:

- **entity**: Entity table with polymorphic entity types
- **relationship**: Relationship table for entity connections
- **paper**: Paper metadata and content
- **evidence**: Evidence items linking papers to relationships

Example:

    >>> from storage.models.entity import EntityTable, EntityType
    >>> from storage.models.relationship import RelationshipTable
    >>>
    >>> # These are persistence models, typically used via mapper functions
    >>> # See mapper.py for domain ↔ persistence conversion

For detailed schema documentation, see models/README.md.
"""

__all__ = [
    "entity",
    "relationship",
    "paper",
    "evidence",
]
