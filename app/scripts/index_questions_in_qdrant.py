#!/usr/bin/env python3
"""
Script pour indexer toutes les questions existantes dans Qdrant.
Pour chaque question dans MySQL :
1. Vérifie si elle est déjà dans Qdrant.
2. Si non, génère son embedding (question + réponse principale) via mistral-embed.
3. Indexe la question dans Qdrant.

Utilisation :
    python scripts/index_questions_in_qdrant.py
"""

import asyncio
import os
import sys

# Ajouter le répertoire parent au path pour importer les modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import (
    get_all_questions_for_indexing,
    is_question_indexed_in_qdrant,
    index_question_in_qdrant,
    ensure_questions_qdrant_collection,
    MISTRAL_EMBED_MODEL,
    MISTRAL_EMBED_DIMENSION,
    QUESTIONS_COLLECTION_PREFIX
)


async def index_all_questions(batch_size: int = 100):
    """
    Indexe toutes les questions de la base MySQL dans Qdrant.
    
    Args:
        batch_size: Nombre de questions à traiter par batch (pour éviter les timeouts).
    """
    print("🚀 Début de l'indexation des questions dans Qdrant...")
    print(f"   Batch size: {batch_size} questions")

    # Initialiser la collection Qdrant
    collection_name = await ensure_questions_qdrant_collection(
        MISTRAL_EMBED_MODEL,
        MISTRAL_EMBED_DIMENSION
    )
    print(f"✅ Collection Qdrant '{collection_name}' prête.")

    # Récupérer toutes les questions
    questions = await get_all_questions_for_indexing()
    print(f"📊 {len(questions)} questions à indexer.")

    if not questions:
        print("⚠️ Aucune question trouvée dans la base de données.")
        return

    # Statistiques
    already_indexed = 0
    newly_indexed = 0
    errors = 0
    total_processed = 0

    # Traiter par batches
    for batch_start in range(0, len(questions), batch_size):
        batch_end = min(batch_start + batch_size, len(questions))
        batch = questions[batch_start:batch_end]
        
        print(f"\n📦 Batch {batch_start // batch_size + 1}/{len(questions) // batch_size + 1} "
              f"(Questions {batch_start + 1}-{batch_end})")

        for i, question in enumerate(batch, 1):
            question_id = question["question_id"]
            print(f"   🔹 Question {batch_start + i}/{len(questions)} (ID: {question_id})")

            # Vérifier si la question est déjà indexée
            if await is_question_indexed_in_qdrant(question_id, collection_name):
                print(f"      ⏭️  Déjà indexée dans Qdrant.")
                already_indexed += 1
                total_processed += 1
                continue

            # Indexer la question
            try:
                metadata = {
                    "status": question["status"],
                    "difficulty_level": question["difficulty_level"],
                    "created_at": str(question["created_at"])
                }

                success = await index_question_in_qdrant(
                    question_id=question_id,
                    content=question["content"],
                    main_answer=question["main_answer"],
                    document_id=question["document_id"],
                    metadata=metadata,
                    collection_name=collection_name
                )

                if success:
                    print(f"      ✅ Indexée dans Qdrant.")
                    newly_indexed += 1
                else:
                    print(f"      ❌ Échec de l'indexation.")
                    errors += 1
                total_processed += 1
            except Exception as e:
                print(f"      ❌ Erreur: {e}")
                errors += 1
                total_processed += 1

    # Résumé
    print("\n" + "=" * 60)
    print("📈 RÉSUMÉ DE L'INDEXATION")
    print("=" * 60)
    print(f"✅ Déjà indexées : {already_indexed}")
    print(f"✅ Nouveau indexées : {newly_indexed}")
    print(f"❌ Erreurs : {errors}")
    print(f"📊 Total traité : {total_processed}/{len(questions)}")
    
    if errors > 0:
        print(f"\n⚠️  {errors} erreurs rencontrées. Vérifiez les logs ci-dessus.")
    else:
        print("\n🎉 Toutes les questions ont été traitées avec succès !")


if __name__ == "__main__":
    # Configurer le batch size (100 par défaut)
    batch_size = 100
    if len(sys.argv) > 1:
        try:
            batch_size = int(sys.argv[1])
        except ValueError:
            print("⚠️  Argument invalide. Utilisation: python index_questions_in_qdrant.py [batch_size]")
            sys.exit(1)
    
    asyncio.run(index_all_questions(batch_size=batch_size))
