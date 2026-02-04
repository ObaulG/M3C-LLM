import asyncio
import logging
from typing import List, Dict, Optional

# Import des fonctions existantes (à adapter selon ton projet)
from database import get_db_connection, save_question_to_db, get_questions_by_document_id, get_chunks_for_document

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fetch_document_questions(
    document_id: str,
    include_answers: bool = True,
    status_filter: Optional[str] = None,
    difficulty_filter: Optional[int] = None,
    theme_filter: Optional[str] = None
) -> List[Dict]:
    """
    Récupère toutes les questions associées à un document.

    Args:
        document_id (str): ID du document.
        conn (asyncpg.Connection): Connexion à la base de données.
        include_answers (bool): Si True, inclut les réponses associées.
        status_filter (Optional[str]): Filtre par statut (ex: "generated", "validated").
        difficulty_filter (Optional[int]): Filtre par niveau de difficulté.
        theme_filter (Optional[str]): Filtre par thème.

    Returns:
        List[Dict]: Liste des questions avec leurs réponses.
    """
    try:
        questions = await get_questions_by_document_id(
            document_id=document_id,
            conn=await get_db_connection(),
            include_answers=include_answers,
            status_filter=status_filter,
            difficulty_filter=difficulty_filter,
            theme_filter=theme_filter
        )
        logger.info(f"Nombre de questions récupérées: {len(questions)}")
        return questions
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des questions: {e}")
        raise

async def display_questions(questions: List[Dict]) -> None:
    """
    Affiche les questions et leurs réponses de manière lisible.

    Args:
        questions (List[Dict]): Liste des questions à afficher.
    """
    if not questions:
        logger.info("Aucune question trouvée.")
        return

    for i, question in enumerate(questions, 1):
        logger.info(f"\n=== Question {i} ===")
        logger.info(f"ID: {question.get('question_id', 'N/A')}")
        logger.info(f"Contenu: {question.get('content', 'N/A')}")
        logger.info(f"Statut: {question.get('status', 'N/A')}")
        logger.info(f"Niveau de difficulté: {question.get('difficulty_level', 'N/A')}")
        logger.info(f"Thème: {question.get('theme', 'N/A')}")
        logger.info(f"Chunk ID: {question.get('chunk_id', 'N/A')}")

        if question.get('answers'):
            logger.info("Réponses:")
            for j, answer in enumerate(question['answers'], 1):
                logger.info(f"  {j}. {answer.get('content', 'N/A')} (Correct: {answer.get('is_correct', 'N/A')})")

async def main():
    """
    Fonction principale pour exécuter le script.
    """
    # 1. Connexion à la base de données
    try:
        # 2. Récupérer les questions pour un document spécifique
        document_id = "dbd5f14a9e6545880b0cd505583ea7d1fe1e8b3d.pdf"
        logger.info(f"Récupération des questions pour le document: {document_id}")

        questions = await fetch_document_questions(
            document_id=document_id,
            include_answers=True,
            status_filter=None,  # Récupérer toutes les questions, quel que soit le statut
            difficulty_filter=None,
            theme_filter=None
        )

        # 3. Afficher les questions
        await display_questions(questions)

        logger.info(f"Questions exportées dans questions_{document_id}.json")

    except Exception as e:
        logger.error(f"Erreur lors de l'exécution du script: {e}")


if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
