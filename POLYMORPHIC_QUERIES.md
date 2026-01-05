# Polymorphic Query Investigation

## Goal

The goal was to enable polymorphic queries on the `Entity` table to allow for cleaner, more ergonomic queries like `session.exec(select(DiseaseEntity)).all()` instead of `session.exec(select(Entity).where(Entity.entity_type == "disease")).all()`.

## Attempts

1.  **Enabled `__mapper_args__`**: The `__mapper_args__` for polymorphic mapping were uncommented in `schema/entity_sqlmodel.py`, and subclasses for each entity type (e.g., `DiseaseEntity`) were created.
2.  **Used `to_persistence` Mapper**: The `to_persistence` mapper was updated to return instances of the correct subclass (e.g., `DiseaseEntity`).
3.  **Direct Instantiation**: Tests were modified to bypass the mapper and instantiate the polymorphic subclasses directly.

## Results

All attempts failed with the same error: `AttributeError: 'NoneType' object has no attribute 'set'` originating from `sqlalchemy/orm/attributes.py`.

This error indicates that the SQLAlchemy ORM is not correctly instrumenting the attributes of the polymorphic subclasses. The exact cause is unclear, but it appears to be a subtle issue related to how SQLModel and SQLAlchemy handle single-table inheritance when the subclasses are defined.

## Decision

Given the difficulty in resolving this issue and the fact that explicit filtering on the `entity_type` column is a viable and performant alternative, the decision has been made to **abandon the implementation of polymorphic queries for now**.

The current approach of using `session.exec(select(Entity).where(Entity.entity_type == "disease"))` is clear, explicit, and works correctly. The minor ergonomic improvement of polymorphic queries does not justify the significant effort required to debug this deep issue within the ORM.

## Next Steps

- The polymorphic configuration in `schema/entity_sqlmodel.py` will be reverted to its disabled state.
- The `tests/test_polymorphic_queries.py` file will be removed.
- The `__init__.py` file in `schema` will be cleaned up.
- The focus will shift to implementing the persistence layer for relationships (Phase 4).
