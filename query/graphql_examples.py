"""
Example GraphQL queries for the Medical Literature Knowledge Graph API.

These queries are displayed in the GraphiQL interface to help users get started.
"""

EXAMPLE_QUERIES = {
    "Get Entity by ID": """# Retrieve a specific entity by its canonical ID
# Returns entire entity as JSON
query GetEntity {
  entity(id: "drug_aspirin")
}""",
    "Search Entities": """# Search for entities with pagination
# Returns array of entities as JSON
query SearchEntities {
  entities(limit: 10, offset: 0)
}""",
    "Find Treatments": """# Find all TREATS relationships
# Returns array of relationships as JSON
query FindTreatments {
  relationships(
    predicate: "TREATS"
    limit: 20
  )
}""",
    "Get Paper": """# Retrieve a research paper by ID
# Returns entire paper as JSON
query GetPaper {
  paper(id: "pmid_12345678")
}""",
    "Filter by Subject": """# Find all relationships for a specific entity
# Returns array of relationships as JSON
query FilterBySubject {
  relationships(
    subjectId: "drug_aspirin"
    limit: 50
  )
}""",
    "Multiple Queries": """# Get an entity and its relationships in one request
# Demonstrates multiple queries in a single operation
query EntityWithRelationships {
  entity(id: "drug_metformin")
  relationships(
    subjectId: "drug_metformin"
    limit: 10
  )
}""",
}

# Default query shown when GraphiQL first loads
DEFAULT_QUERY = EXAMPLE_QUERIES["Search Entities"]
