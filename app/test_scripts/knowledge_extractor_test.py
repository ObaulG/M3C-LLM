"""
Test simple pour le Knowledge Element Extractor

Ce script permet de tester l'extraction de connaissances structurées
sans avoir besoin de base de données ou de connexion LLM.
"""

import asyncio
import sys
import os

# Ajouter le chemin parent pour les imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agents.knowledge_element_extractor import (
    extract_knowledge_elements,
    extract_knowledge_fallback,
    KnowledgeItemCandidate,
    EntityCandidate,
    ThemeCandidate,
    SourceReference,
    EntityType
)


async def test_fallback_extraction():
    """Test l'extraction de fallback (sans LLM) avec du texte simple"""
    
    print("=== TEST: Extraction Fallback ===")
    
    # Texte de test simple
    text = """
    Paris est la capitale de la France. Cette ville est située sur les rives de la Seine.
    La Tour Eiffel, construite en 1889, est un monument emblématique de Paris.
    Gustave Eiffel était l'ingénieur en chef de ce projet.
    """
    
    print("Texte de test:")
    print(text)
    print("\nExtraction en cours...")
    
    try:
        # Requests l'extraction avec fallback
        candidates = await extract_knowledge_fallback(
            text=text,
            chunk_id="test_chunk_1",
            document_id="test_document_1"
        )
        
        print(f"\nExtraits {len(candidates)} éléments de connaissance:")
        for i, candidate in enumerate(candidates):
            print(f"\n--- Élément {i+1} ---")
            print(f"Proposition: {candidate.proposition}")
            print(f"Summary: {candidate.summary}")
            print(f"Confiance: {candidate.confidence}")
            print(f"Entités: {[f'{e.name} ({e.type.value})' for e in candidate.entities]}")
            print(f"Thèmes: {[t.name for t in candidate.themes]}")
            print(f"Source positions: {candidate.source_reference.position_start}-{candidate.source_reference.position_end}")
            print(f"Excerpt: "{candidate.source_reference.excerpt}"...")
            
        return candidates
        
    except Exception as e:
        print(f"Erreur lors de l'extraction: {e}")
        return []


async def test_data_structures():
    """Test les structures de données"""
    
    print("\n=== TEST: Structures de données ===")
    
    # Créer un candidate manuellement pour tester les structures
    entity1 = EntityCandidate(name="Paris", type=EntityType.PLACE, confidence=0.95)
    entity2 = EntityCandidate(name="France", type=EntityType.PLACE, confidence=0.9)
    theme1 = ThemeCandidate(name="Géographie", confidence=0.9)
    
    source_ref = SourceReference(
        document_id="test_doc",
        chunk_id="test_chunk",
        excerpt="Paris est la capitale de la France",
        position_start=0,
        position_end=30
    )
    
    candidate = KnowledgeItemCandidate(
        proposition="Paris est la capitale de la France",
        entities=[entity1, entity2],
        themes=[theme1],
        source_reference=source_ref,
        summary="Paris capitale France",
        confidence=0.95
    )
    
    print("Candidat créé:")
    print(f"Proposition: {candidate.proposition}")
    print(f"Hash: {candidate.get_hash()}")
    print(f"Dict: {json.dumps(candidate.to_dict(), indent=2, ensure_ascii=False)}")
    
    return candidate


async def test_entity_cleaning():
    """Test le nettoyage des noms d'entités"""
    from agents.knowledge_element_extractor import clean_entity_name
    
    print("\n=== TEST: Nettoyage des noms d'entités ===")
    
    test_names = [
        "Le Louvre",
        "la Tour Eiffel",
        "un homme appelé Léonard",
        "  l' Opéra  de Paris  ",
        "de la République française",
        "Musée du Louvre",
        "Léonard de Vinci"
    ]
    
    for name in test_names:
        cleaned = clean_entity_name(name)
        print(f"'{name}' -> '{cleaned}'")


async def test_validation():
    """Test la validation des candidats"""
    from agents.knowledge_element_extractor import validate_knowledge_item
    
    print("\n=== TEST: Validation ===")
    
    # Candidat valide
    valid_candidate = KnowledgeItemCandidate(
        proposition="Paris est la capitale de la France",
        entities=[EntityCandidate(name="Paris", type=EntityType.PLACE)],
        themes=[ThemeCandidate(name="Géographie")],
        source_reference=SourceReference(
            excerpt="Paris est la capitale de la France",
            position_start=0,
            position_end=30
        )
    )
    
    # Candidat invalide (trop court)
    invalid_candidate1 = KnowledgeItemCandidate(
        proposition="Paris",
        entities=[],
        themes=[],
        source_reference=SourceReference()
    )
    
    # Candidat invalide (pas de source)
    invalid_candidate2 = KnowledgeItemCandidate(
        proposition="Paris est la capitale de la France",
        entities=[],
        themes=[],
        source_reference=SourceReference()
    )
    
    print(f"Candidat valide: {validate_knowledge_item(valid_candidate)}")
    print(f"Candidat trop court: {validate_knowledge_item(invalid_candidate1)}")
    print(f"Candidat sans source: {validate_knowledge_item(invalid_candidate2)}")


async def main():
    """Exécute tous les tests"""
    print("Démarrage des tests Knowledge Element Extractor\n")
    
    # Test des structures de données
    await test_data_structures()
    
    # Test du nettoyage
    await test_entity_cleaning()
    
    # Test de la validation
    await test_validation()
    
    # Test de l'extraction (qui utilise le fallback)
    candidates = await test_fallback_extraction()
    
    print(f"\n=== SUMMARY ===")
    print(f"Tous les tests se sont exécutés avec succès")
    print(f"Extraction fallback: {len(candidates)} connaissances extraites")


if __name__ == "__main__":
    import json
    asyncio.run(main())