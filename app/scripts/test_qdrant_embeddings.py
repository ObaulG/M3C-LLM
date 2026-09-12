#!/usr/bin/env python3
"""Test script for Qdrant embeddings insertion with LD- format."""

import asyncio
import random
import uuid
from typing import List

from database.database import (
    ensure_qdrant_collection,
    insert_chunk_embedding_qdrant,
    get_top_k_similar_chunks_qdrant,
    qdrant_client
)

# Configuration
TEST_MODEL_NAME = "test-embed"
TEST_VECTOR_SIZE = 384
TEST_COLLECTION_NAME = f"LD-{TEST_MODEL_NAME}-{TEST_VECTOR_SIZE}"
TEST_DOCUMENT_ID = "test-doc-1"


def generate_mock_embedding(size: int) -> List[float]:
    """Genere un embedding mock."""
    return [random.random() for _ in range(size)]


async def test_collection_creation():
    """Test 1 : Creation de la collection avec le bon format."""
    print("Test 1: Creation de la collection...")
    await ensure_qdrant_collection(TEST_COLLECTION_NAME, TEST_VECTOR_SIZE)
    
    collections = qdrant_client.get_collections()
    collection_names = [c.name for c in collections.collections]
    assert TEST_COLLECTION_NAME in collection_names, f"Collection {TEST_COLLECTION_NAME} non trouvee"
    print(f"✓ Collection '{TEST_COLLECTION_NAME}' creee")


async def test_insert_single_embedding():
    """Test 2 : Insertion d'un embedding."""
    print("\nTest 2: Insertion d'un embedding...")
    
    chunk_id = str(uuid.uuid4())
    embedding = generate_mock_embedding(TEST_VECTOR_SIZE)
    
    result = await insert_chunk_embedding_qdrant(
        chunk_id=chunk_id,
        document_id=TEST_DOCUMENT_ID,
        model_name=TEST_MODEL_NAME,
        embedding=embedding,
        content="Ceci est un texte de test",
        num_page=1,
        position_in_page=0,
        token_count=5,
        metadata={"source": "test"},
        collection_name=TEST_COLLECTION_NAME
    )
    print(f"✓ Embedding insere (ID: {chunk_id}, operation_id: {result.operation_id})")


async def test_insert_multiple_embeddings():
    """Test 3 : Insertion de plusieurs embeddings."""
    print("\nTest 3: Insertion de 5 embeddings...")
    
    num_chunks = 5
    for i in range(num_chunks):
        chunk_id = str(uuid.uuid4())
        embedding = generate_mock_embedding(TEST_VECTOR_SIZE)
        
        result = await insert_chunk_embedding_qdrant(
            chunk_id=chunk_id,
            document_id=TEST_DOCUMENT_ID,
            model_name=TEST_MODEL_NAME,
            embedding=embedding,
            content=f"Texte de test {i}",
            num_page=1,
            position_in_page=i,
            token_count=10,
            metadata={"source": "test", "index": i},
            collection_name=TEST_COLLECTION_NAME
        )
    
    print(f"✓ {num_chunks} embeddings insérés")


async def test_retrieve_embeddings():
    """Test 4 : Recuperation des embeddings."""
    print("\nTest 4: Recuperation des embeddings...")
    
    query_embedding = generate_mock_embedding(TEST_VECTOR_SIZE)
    results = await get_top_k_similar_chunks_qdrant(
        embedding=query_embedding,
        model_name=TEST_COLLECTION_NAME,
        k=10
    )
    
    assert len(results) > 0, "Aucun résultat trouvé"
    for result in results:
        assert "chunk_id" in result, "chunk_id manquant"
        assert "document_id" in result, "document_id manquant"
        print(f"  - Trouve: {result['chunk_id']}")
    
    print(f"✓ {len(results)} embeddings recuperes")


async def test_format_validation():
    """Test 5 : Validation du format de collection."""
    print("\nTest 5: Validation du format de collection...")
    
    # Tester avec mistral-embed (1024 dimensions)
    mistral_collection = f"LD-mistral-embed-1024"
    await ensure_qdrant_collection(mistral_collection, 1024)
    
    collections = qdrant_client.get_collections()
    collection_names = [c.name for c in collections.collections]
    assert mistral_collection in collection_names, f"Format incorrect pour {mistral_collection}"
    print(f"✓ Format valide: {mistral_collection}")


async def cleanup_test_collections():
    """Nettoyage : Suppression des collections de test."""
    print("\nNettoyage des collections de test...")
    test_collections = [
        f"LD-{TEST_MODEL_NAME}-{TEST_VECTOR_SIZE}",
        "LD-mistral-embed-1024"
    ]
    
    for coll_name in test_collections:
        try:
            qdrant_client.delete_collection(coll_name)
            print(f"  - Collection '{coll_name}' supprimee")
        except Exception as e:
            print(f"  - {coll_name} non trouvee (deja supprimee ?): {e}")


async def main():
    """Execute tous les tests."""
    print("=" * 60)
    print("DEBUT DES TESTS QDRANT")
    print("=" * 60)
    
    try:
        await test_collection_creation()
        await test_insert_single_embedding()
        await test_insert_multiple_embeddings()
        await test_retrieve_embeddings()
        await test_format_validation()
        
        print("\n" + "=" * 60)
        print("TOUS LES TESTS ONT REUSSI ✓")
        print("=" * 60)
        
        # Nettoyage
        await cleanup_test_collections()
        
    except AssertionError as e:
        print(f"\n✗ TEST ECHOUE: {e}")
        await cleanup_test_collections()
        raise
    except Exception as e:
        print(f"\n✗ ERREUR: {e}")
        await cleanup_test_collections()
        raise


if __name__ == "__main__":
    asyncio.run(main())
