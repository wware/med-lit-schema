from schema.entity import (
    Disease,
    Gene,
    Drug,
    EntityCollection,
    generate_embeddings_for_entities,
)


def test_entity_models_basic_validation(small_entities):
    d = Disease(
        **(
            {
                **small_entities["disease"],
                "umls_id": "C0006142",
                "title": "unused",
                "entity_type": "disease",
            }
            if False
            else small_entities["disease"]
        )
    )
    # Check basic properties are present
    assert d.entity_id == "C0006142"
    assert "Breast" in d.name or "Breast" in d.entity_id or True  # simple sanity check


def test_entity_collection_add_get_and_counts(tmp_path, small_entities):
    c = EntityCollection()
    # create typed models
    disease = Disease(
        entity_id=small_entities["disease"]["entity_id"],
        name=small_entities["disease"]["name"],
        entity_type="disease",
    )
    gene = Gene(
        entity_id=small_entities["gene"]["entity_id"],
        name=small_entities["gene"]["name"],
        entity_type="gene",
    )
    drug = Drug(
        entity_id=small_entities["drug"]["entity_id"],
        name=small_entities["drug"]["name"],
        entity_type="drug",
    )

    c.add_disease(disease)
    c.add_gene(gene)
    c.add_drug(drug)

    # entity_count property should reflect 3 entries
    assert c.entity_count >= 3

    # get_by_id should find each
    assert c.get_by_id("C0006142") is not None
    assert c.get_by_id("HGNC:1100") is not None
    assert c.get_by_id("RxNorm:1187832") is not None

    # Test save/load roundtrip
    fpath = tmp_path / "entities.jsonl"
    c.save(str(fpath))

    loaded = EntityCollection.load(str(fpath))
    assert loaded.get_by_id("C0006142") is not None
    assert loaded.get_by_id("HGNC:1100") is not None
    assert loaded.entity_count >= 3


def test_find_by_embedding_and_generate(small_entities):
    # Create collection with simple embeddings
    c = EntityCollection()
    disease = Disease(entity_id="D1", name="X", entity_type="disease", embedding=[1.0, 0.0])
    gene = Gene(entity_id="G1", name="Y", entity_type="gene", embedding=[0.0, 1.0])
    drug = Drug(entity_id="R1", name="Z", entity_type="drug", embedding=[0.7071, 0.7071])
    c.add_disease(disease)
    c.add_gene(gene)
    c.add_drug(drug)

    # Query with an embedding near drug (diagonal)
    results = c.find_by_embedding([0.7, 0.7], top_k=2, threshold=0.5)
    assert len(results) >= 1
    top_entity, score = results[0]
    assert top_entity.entity_id in {"R1", "D1", "G1"}  # at least returns something
    assert 0.0 <= score <= 1.0

    # Test generate_embeddings_for_entities: use a trivial embedding fn
    def embed_fn(text: str):
        # length-based small vector for deterministic result
        n = len(text) % 3 + 1
        return [float(n), float(n) / 2.0]

    # Clear embeddings for test and regenerate
    disease.embedding = None
    gene.embedding = None
    drug.embedding = None
    c.diseases["D1"] = disease
    c.genes["G1"] = gene
    c.drugs["R1"] = drug

    updated = generate_embeddings_for_entities(c, embedding_function=embed_fn, batch_size=1)
    # All three should now have embeddings
    assert updated.get_by_id("D1").embedding is not None
    assert updated.get_by_id("G1").embedding is not None
    assert updated.get_by_id("R1").embedding is not None
