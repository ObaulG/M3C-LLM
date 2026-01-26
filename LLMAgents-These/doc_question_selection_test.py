import asyncio
import logging
from typing import List, Dict, Optional, Tuple

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Import des fonctions existantes (à adapter selon ton projet)
from database import (
    get_db_connection,
    get_questions_by_document_id,
    get_chunks_for_document,
)

async def select_questions_with_context(
    document_id: str,
    num_questions: int = 3,
    min_similarity_threshold: float = 0.7
) -> List[Tuple[Dict, Optional[str]]]:
    """
    Sélectionne un nombre de questions pour un document et retourne chaque question
    avec la portion de document pertinente (contenu du chunk associé).

    Args:
        document_id (str): ID du document.
        num_questions (int): Nombre de questions à sélectionner.
        min_similarity_threshold (float): Seuil de similarité pour filtrer les questions.

    Returns:
        List[Tuple[Dict, Optional[str]]]: Liste de tuples (question, contenu_du_chunk).
    """
    conn = None
    try:
        conn = await get_db_connection()
        questions = await get_questions_by_document_id(
            document_id=document_id,
            conn=conn,
            include_answers=True,
            nb_limit=num_questions
        )

        if not questions:
            logger.warning(f"Aucune question validée trouvée pour le document {document_id}.")
            return []

        # 3. Sélectionner les `num_questions` premières questions (ou moins si pas assez)
        selected_questions = questions[:num_questions]

        return selected_questions

    except Exception as e:
        logger.error(f"Erreur lors de la sélection des questions: {e}")
        return []
    finally:
        if conn:
            await conn.close()

async def display_questions_with_context(questions_with_context: List[Tuple[Dict, Optional[str]]]) -> None:
    """
    Affiche les questions sélectionnées avec leur contexte (portion de document).

    Args:
        questions_with_context (List[Tuple[Dict, Optional[str]]]): Liste de questions avec leur contexte.
    """
    if not questions_with_context:
        logger.info("Aucune question à afficher.")
        return

    for i, question in enumerate(questions_with_context):
        logger.info(f"\n{'='*60}")
        logger.info(f"Question {i}: {question.get('content', 'N/A')}")
        logger.info(f"ID: {question.get('question_id', 'N/A')}")
        logger.info(f"Statut: {question.get('status', 'N/A')}")
        logger.info(f"Niveau de difficulté: {question.get('difficulty_level', 'N/A')}")
        logger.info(f"Thème: {question.get('theme', 'N/A')}")

        if question.get('answers'):
            logger.info("Réponses:")
            for j, answer in enumerate(question['answers'], 1):
                logger.info(f"  {j}. {answer.get('content', 'N/A')} (Correct: {answer.get('is_correct', 'N/A')})")

        logger.info(f"\nContexte (portion du document): chunk_id:{question.get('chunk_id', 'N/A')}")


async def main():
    """
    Fonction principale pour exécuter le script.
    """
    try:
        # 1. Paramètres de sélection
        document_id = "dbd5f14a9e6545880b0cd505583ea7d1fe1e8b3d.pdf"  # ID du document
        num_questions = 15  # Nombre de questions à sélectionner

        logger.info(f"Sélection de {num_questions} questions pour le document: {document_id}")

        # 2. Sélectionner les questions avec leur contexte
        questions_with_context = await select_questions_with_context(
            document_id=document_id,
            num_questions=num_questions
        )
        logger.info("Questions générées")
        # 3. Afficher les questions avec leur contexte
        await display_questions_with_context(questions_with_context)

    except Exception as e:
        logger.error(f"Erreur lors de l'exécution du script: {e}")

if __name__ == "__main__":
    # Configuration pour Windows (nécessaire pour asyncio sur Windows)
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
