"""
Enhanced Entity SQLModel with JSONB properties, pgvector support, and advanced features.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import Field, SQLModel, Column, Index
from sqlalchemy import JSON, text
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector


class Entity(SQLModel, table=True):
    """
    Enhanced Entity model with flexible properties storage and vector embeddings.
    
    Features:
    - JSONB properties field for flexible metadata
    - pgvector support for semantic search
    - Auto-updating timestamps
    - Canonical ID for entity resolution
    - Proper indexes for query optimization
    """
    
    __tablename__ = "entities"
    
    # Primary identifier
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        index=True,
        description="Auto-incrementing primary key"
    )
    
    # Entity type and name
    entity_type: str = Field(
        index=True,
        max_length=100,
        description="Type of entity (e.g., 'gene', 'disease', 'drug', 'protein')"
    )
    
    name: str = Field(
        index=True,
        max_length=500,
        description="Primary name or label for the entity"
    )
    
    # Canonical ID for entity resolution
    canonical_id: Optional[str] = Field(
        default=None,
        index=True,
        max_length=200,
        description="Canonical identifier for entity resolution (e.g., MESH:D000001)"
    )
    
    # Flexible properties storage using JSONB
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
            comment="Flexible JSONB field for entity metadata and attributes"
        )
    )
    
    # Vector embedding for semantic search (1536 dimensions for OpenAI embeddings)
    embedding: Optional[list[float]] = Field(
        default=None,
        sa_column=Column(
            Vector(1536),
            nullable=True,
            comment="Vector embedding for semantic similarity search"
        )
    )
    
    # Source information
    source: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Source database or system (e.g., 'PubMed', 'UniProt')"
    )
    
    source_id: Optional[str] = Field(
        default=None,
        index=True,
        max_length=200,
        description="External identifier in the source system"
    )
    
    # Confidence score for entity extraction
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score for entity extraction (0.0 to 1.0)"
    )
    
    # Auto-updating timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            sa_type=None,  # Let SQLModel infer the type
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
            comment="Timestamp when the entity was created"
        )
    )
    
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            sa_type=None,  # Let SQLModel infer the type
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=datetime.utcnow,
            comment="Timestamp when the entity was last updated"
        )
    )
    
    # Soft delete flag
    is_active: bool = Field(
        default=True,
        index=True,
        description="Flag for soft deletes"
    )
    
    # Additional metadata
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of the entity"
    )
    
    aliases: Optional[str] = Field(
        default=None,
        description="Comma-separated list of alternative names"
    )
    
    # Define indexes for better query performance
    __table_args__ = (
        # Composite index for type + name queries
        Index("ix_entities_type_name", "entity_type", "name"),
        
        # Composite index for source lookups
        Index("ix_entities_source_sourceid", "source", "source_id"),
        
        # Index for active entities by type
        Index("ix_entities_active_type", "is_active", "entity_type"),
        
        # GIN index for JSONB properties (requires PostgreSQL)
        Index("ix_entities_properties_gin", "properties", postgresql_using="gin"),
        
        # Index for canonical ID lookups
        Index("ix_entities_canonical", "canonical_id", unique=False),
        
        # Vector similarity search index (IVFFlat for pgvector)
        Index(
            "ix_entities_embedding_vector",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"}
        ),
    )
    
    class Config:
        """SQLModel configuration"""
        json_schema_extra = {
            "example": {
                "entity_type": "gene",
                "name": "BRCA1",
                "canonical_id": "HGNC:1100",
                "properties": {
                    "full_name": "breast cancer 1, early onset",
                    "chromosome": "17",
                    "location": "17q21.31",
                    "gene_family": "BRCA1/2",
                    "function": "DNA repair"
                },
                "source": "HGNC",
                "source_id": "1100",
                "confidence": 0.98,
                "description": "BRCA1 is a human tumor suppressor gene",
                "aliases": "BRCC1,FANCS,PNCA4,RNF53",
                "is_active": True
            }
        }
    
    def __repr__(self) -> str:
        """String representation of the entity"""
        return f"<Entity(id={self.id}, type={self.entity_type}, name={self.name})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary representation"""
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "name": self.name,
            "canonical_id": self.canonical_id,
            "properties": self.properties,
            "source": self.source,
            "source_id": self.source_id,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active,
            "description": self.description,
            "aliases": self.aliases
        }


class EntityCreate(SQLModel):
    """Schema for creating new entities"""
    entity_type: str = Field(max_length=100)
    name: str = Field(max_length=500)
    canonical_id: Optional[str] = Field(default=None, max_length=200)
    properties: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[list[float]] = None
    source: Optional[str] = Field(default=None, max_length=200)
    source_id: Optional[str] = Field(default=None, max_length=200)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    description: Optional[str] = None
    aliases: Optional[str] = None


class EntityUpdate(SQLModel):
    """Schema for updating entities"""
    name: Optional[str] = Field(default=None, max_length=500)
    canonical_id: Optional[str] = Field(default=None, max_length=200)
    properties: Optional[Dict[str, Any]] = None
    embedding: Optional[list[float]] = None
    source: Optional[str] = Field(default=None, max_length=200)
    source_id: Optional[str] = Field(default=None, max_length=200)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_active: Optional[bool] = None
    description: Optional[str] = None
    aliases: Optional[str] = None


class EntityRead(SQLModel):
    """Schema for reading entities (response model)"""
    id: int
    entity_type: str
    name: str
    canonical_id: Optional[str]
    properties: Dict[str, Any]
    source: Optional[str]
    source_id: Optional[str]
    confidence: Optional[float]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    description: Optional[str]
    aliases: Optional[str]
