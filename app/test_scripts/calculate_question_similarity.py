#!/usr/bin/env python3
"""
Script to calculate cosine similarity between two questions.

This script provides multiple ways to calculate similarity:
1. Direct text comparison using embeddings
2. Database-based comparison using stored question embeddings
3. Hybrid approach combining both methods

Usage:
    python calculate_question_similarity.py [options]

Examples:
    # Compare two questions by text
    python calculate_question_similarity.py --text "What is AI?" "How does artificial intelligence work?"
    
    # Compare two questions by their IDs from database
    python calculate_question_similarity.py --question-ids 123 456
    
    # Compare using both methods
    python calculate_question_similarity.py --text "What is AI?" "How does artificial intelligence work?" --question-ids 123 456
"""

import asyncio
import argparse
from itertools import combinations

import numpy as np
from typing import Tuple, Optional, List
import psycopg
from sklearn.metrics.pairwise import cosine_similarity
import database.database as database


# Try to import Mistral embeddings for direct text comparison
try:
    from langchain_mistralai import MistralAIEmbeddings
    EMBEDDING_AVAILABLE = True
    embedder = MistralAIEmbeddings(model="mistral-embed")
except ImportError:
    EMBEDDING_AVAILABLE = False
    print("Warning: MistralAIEmbeddings not available. Direct text comparison will be disabled.")

async def compare_all_questions(questions: List[Tuple[int, str]], threshold: float = 0.75) -> List[Tuple[Tuple[int, str], Tuple[int, str], float]]:
    """
    Compare toutes les paires de questions et retourne celles dont la similarité dépasse le seuil.

    Args:
        questions: Liste de tuples (id, texte) représentant les questions.
        threshold: Seuil de similarité (par défaut 0.75).

    Returns:
        Liste de tuples (question1, question2, score) pour les paires similaires.
    """
    similar_pairs = []

    # Générer toutes les paires possibles
    for (id1, text1) , (id2, text2) in combinations(questions, 2):
        similarity = await compare_questions_by_text(text1, text2)
        if similarity is not None and similarity > threshold:
            similar_pairs.append((id1, id2, similarity))

    return similar_pairs

def calculate_cosine_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """
    Calculate cosine similarity between two embeddings.
    
    Args:
        embedding1: First embedding as numpy array
        embedding2: Second embedding as numpy array
        
    Returns:
        Cosine similarity score between -1 and 1 (1 = most similar)
    """
    # Reshape embeddings to 2D arrays (required by sklearn)
    embedding1_2d = embedding1.reshape(1, -1)
    embedding2_2d = embedding2.reshape(1, -1)
    
    # Calculate cosine similarity
    similarity = cosine_similarity(embedding1_2d, embedding2_2d)[0][0]
    
    return similarity

def get_text_embedding(text: str) -> Optional[np.ndarray]:
    """
    Get embedding for a text using Mistral embeddings.
    
    Args:
        text: Text to embed
        
    Returns:
        numpy array containing the embedding, or None if embeddings are not available
    """
    if not EMBEDDING_AVAILABLE:
        print("Text embeddings are not available. Install langchain_mistralai to enable this feature.")
        return None
    
    try:
        embedding = embedder.embed_documents([str(text)])[0]
        return np.array(embedding)
    except Exception as e:
        print(f"Error generating text embedding: {e}")
        return None

async def compare_questions_by_text(text1: str, text2: str) -> Optional[float]:
    """
    Compare two questions by their text content using embeddings.
    
    Args:
        text1: First question text
        text2: Second question text
        
    Returns:
        Cosine similarity score, or None if comparison failed
    """
    print(f"Comparing questions by text:")
    print(f"  Question 1: '{text1}'")
    print(f"  Question 2: '{text2}'")
    
    embedding1 = get_text_embedding(text1)
    embedding2 = get_text_embedding(text2)
    
    if embedding1 is None or embedding2 is None:
        return None
    
    similarity = calculate_cosine_similarity(embedding1, embedding2)
    print(f"  Text-based similarity: {similarity:.4f}")
    
    return similarity


async def main():
    """Main function to handle command line arguments and execute comparison."""
    parser = argparse.ArgumentParser(
        description="Calculate cosine similarity between two questions.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        "--show-text",
        action="store_true",
        help="Show the text of questions when comparing by ID"
    )
    
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Similarity threshold for considering questions similar (default: 0.5)"
    )
    
    args = parser.parse_args()

    document_id = "8a672d2ae6f2abfa4434e0f4145a9aa77bbc6d56"

    questions = await database.get_questions_by_document_id(document_id,
                                                      await database.get_db_connection())
    questions = [(q["question_id"], q["content"]) for q in questions]
    print("Question Similarity Calculator")
    print("=" * 50)
    print("\nSimilarity scale:")
    print("  1.0 = Identical or very similar")
    print("  0.7-0.9 = Quite similar")
    print("  0.5-0.7 = Somewhat similar")
    print("  0.3-0.5 = Weak similarity")
    print("  0.0-0.3 = Very different")

    similar_pairs = await compare_all_questions(questions, args.threshold)

    if not similar_pairs:
        print("No similar pairs found above the threshold.")
    else:
        print(f"Found {len(similar_pairs)} similar pairs (threshold: {args.threshold}):")
        for (id1, text1), (id2, text2), score in similar_pairs:
            print(f"\nPair (similarity: {score:.4f}):")
            print(f"  Question {id1}: '{text1}'")
            print(f"  Question {id2}: '{text2}'")


async def test_few_questions():
    q1 = "Quels sont les deux éléments naturels principaux qui interagissent selon le texte pour donner une identité particulière à la Corse, et comment ces interactions sont-elles décrites ?"
    embed1 = get_text_embedding(q1)
    q_compare = [
        "En quoi la phrase utilise-t-elle une structure linguistique particulière pour souligner l'importance de ces interactions ?",
        "Selon le texte, quelle est la conséquence globale de ces interactions entre la montagne et la mer pour la Corse ?",
        "Quels sont les deux éléments naturels qui interagissent réciproquement selon le texte pour donner à la Corse une physionomie unique ?",
        "Selon le texte, comment la nature et l'histoire de la Corse sont-elles liées à travers ces interactions ?",
        "Quelle métaphore ou image la poésie utilise-t-elle pour décrire l'effet de cette interaction entre la montagne et la mer sur l'identité de la Corse ?",
        "Quels sont les deux éléments naturels qui influencent la physionomie de la Corse selon le texte ?",
        "Comment la montagne et la mer interagissent-elles pour façonner la Corse ?",
        "Quelle est l'importance de la nature et de l'histoire dans la formation de la physionomie de la Corse ?",
        "Quels sont les deux éléments géographiques principaux qui interagissent pour façonner la physionomie de la Corse selon le texte ?",
        "Pourquoi la Corse est-elle décrite comme ayant une physionomie \"si originale et si grandiose\" ?",
        "Quel rôle joue le \"sol\" dans la formation de l'identité naturelle et historique de la Corse selon l'extrait ?",
        "Comment la montagne et la mer influencent-elles la physionomie de la Corse ?",
        "Quel rôle joue le sol dans l'interaction entre la montagne et la mer en Corse ?",
        "En quoi la nature et l'histoire de la Corse sont-elles influencées par la montagne et la mer ?",
        "Comment la relation entre la montagne et la mer contribue-t-elle à façonner l'identité géographique et historique de la Corse, selon le texte ?",
        ]
    embed_compare = [get_text_embedding(q) for q in q_compare]
    for (q, e) in zip(q_compare, embed_compare):
        sim = await compare_questions_by_text(q1, q)
        print(sim)
if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    #asyncio.run(main())
    asyncio.run(test_few_questions())