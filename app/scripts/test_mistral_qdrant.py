#!/usr/bin/env python3
"""Test script for Qdrant embeddings insertion with Mistral API."""

import asyncio
import os
import uuid

from database.database import (
    ensure_qdrant_collection,
    insert_chunk_embedding_qdrant,
    get_top_k_similar_chunks_qdrant,
    qdrant_client
)
from embedders import get_embedder_instance

# Configuration
MODEL_NAME = "mistral-embed"
VECTOR_SIZE = 1024  # Mistral embed dimension
COLLECTION_NAME = f"LD-{MODEL_NAME}-{VECTOR_SIZE}"
DOCUMENT_ID = "mistral-test-doc"

# Textes de test
TEST_TEXTS = [
    "L'intelligence artificielle révolutionne de nombreux secteurs.",
    "Les modèles de langage comme Mistral permettent des applications innovantes.",
    "L'indexation de documents avec des embeddings améliore la recherche sémantique.",
    "Qdrant est une base de données vectorielles performante.",
    "Le format LD-{model}-{dimension} permet une bonne organisation des collections."
]


async def test_mistral_embeddings():
    """Test avec l'API Mistral-embed."""
    print("=" * 60)
    print("TEST MISTRAL EMBEDDINGS -> QDRANT")
    print("=" * 60)
    
    # Vérifier que la clé API est disponible
    if not os.getenv("MISTRAL_API_KEY"):
        print("⚠ MISTRAL_API_KEY non trouvée dans les variables d'environnement")
        print("  Pour exécuter ce test, exportez la variable :")
        print("  export MISTRAL_API_KEY=votre_cle_api")
        return
    
    # Récupérer l'embedder
    print("\n1. Initialisation de l'embedder Mistral...")
    try:
        embedder = get_embedder_instance("mistral-embed")
        print(f"   ✓ Embedder chargé: {embedder.name}")
        print(f"   ✓ Dimension: {embedder.dimension}")
    except Exception as e:
        print(f"   ✗ Erreur lors du chargement de l'embedder: {e}")
        return
    
    # Créer la collection
    print("\n2. Création de la collection Qdrant...")
    try:
        await ensure_qdrant_collection(COLLECTION_NAME, VECTOR_SIZE)
        print(f"   ✓ Collection '{COLLECTION_NAME}' prête")
    except Exception as e:
        print(f"   ✗ Erreur création collection: {e}")
        return
    
    # Générer et insérer les embeddings
    print("\n3. Génération et insertion des embeddings...")
    success_count = 0
    
    for i, text in enumerate(TEST_TEXTS):
        chunk_id = str(uuid.uuid4())
        try:
            # Générer l'embedding avec Mistral
            embedding = embedder.embed(text)
            print(f"   - Embedding généré pour le texte {i+1}/{len(TEST_TEXTS)}")
            
            # Insérer dans Qdrant
            result = await insert_chunk_embedding_qdrant(
                chunk_id=chunk_id,
                document_id=DOCUMENT_ID,
                model_name=MODEL_NAME,
                embedding=embedding,
                content=text,
                num_page=1,
                position_in_page=i,
                token_count=len(text.split()),
                metadata={"source": "test_mistral", "text_length": len(text), "index": i},
                collection_name=COLLECTION_NAME
            )
            print(f"   ✓ Chunk {i+1} inséré avec succès (operation_id: {result.operation_id})")
            success_count += 1
                
        except Exception as e:
            print(f"   ✗ Erreur pour le texte {i}: {e}")
    
    # Résumé
    print("\n4. Résumé:")
    print(f"   - Textes traités: {len(TEST_TEXTS)}")
    print(f"   - Embeddings insérés: {success_count}")
    
    if success_count == len(TEST_TEXTS):
        print("   ✓ TOUS LES EMBEDDINGS ONT ETE INSERES AVEC SUCCES")
    else:
        print(f"   ✗ Embeddings manquants")
    
    # Tester la récupération
    print("\n5. Test de récupération...")
    try:
        # Prendre le premier embedding comme requête
        query_embedding = embedder.embed(TEST_TEXTS[0])
        
        results = await get_top_k_similar_chunks_qdrant(
            embedding=query_embedding,
            model_name=COLLECTION_NAME,
            k=3
        )
        
        print(f"   ✓ {len(results)} résultats trouvés")
        for i, result in enumerate(results):
            print(f"     {i+1}. {result.get('content', 'N/A')[:60]}...")
            print(f"        - Similarité: {result.get('similarity', 0):.4f}")
            print(f"        - Chunk ID: {result.get('chunk_id')}")
    except Exception as e:
        print(f"   ✗ Erreur lors de la récupération: {e}")
    
    # Nettoyage
    print("\n6. Nettoyage...")
    try:
        qdrant_client.delete_collection(COLLECTION_NAME)
        print(f"   ✓ Collection '{COLLECTION_NAME}' supprimée")
    except Exception as e:
        print(f"   ⚠ Impossible de supprimer la collection: {e}")
    
    print("\n" + "=" * 60)
    print("TEST TERMINE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_mistral_embeddings())
