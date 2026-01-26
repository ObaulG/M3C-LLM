import asyncio

import logging
from typing import List, Dict, Optional

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import des fonctions existantes (à adapter selon ton projet)
from agents.qa_agent import get_qa_agent, QuestionRequestInput, QuestionAnswerList
from database import get_db_connection, save_question_to_db, get_questions_by_document_id, get_chunks_for_document

# Constantes
DOCUMENT_ID = "dbd5f14a9e6545880b0cd505583ea7d1fe1e8b3d.pdf"
DIFFICULTY_LEVEL = 3  # Niveau de difficulté par défaut

async def generate_and_save_questions(
    document_content: str,
    chunk_id: str,
    num_questions: int = 3,
    ) -> List[Dict]:
    """
    Génère des questions/réponses à partir d'un document et les sauvegarde en base de données.

    Args:
        document_content (str): Contenu du document.
        num_questions (int): Nombre de questions à générer.

    Returns:
        List[Dict]: Liste des questions/réponses sauvegardées.
    """
    # 1. Initialiser l'agent de génération de questions
    qa_agent = get_qa_agent(model="mistral-medium")

    # 2. Générer les questions/réponses
    input_schema = QuestionRequestInput(
        message=f"Génère {num_questions} questions diversifiées sur le document.",
        document=document_content
    )
    print("running agent")

    response = qa_agent.run(input_schema)

    # 3. Sauvegarder les questions/réponses en base de données
    saved_questions = []
    for qa in response.questions_answers:
        try:
            await save_question_to_db(
                question=qa.question_text,
                answer=qa.answer_text,
                chunk_id=chunk_id,
                conn=await get_db_connection(),
                difficulty_level=DIFFICULTY_LEVEL,
            )
            saved_questions.append({
                "question": qa.question_text,
                "answer": qa.answer_text,
                "status": "generated",
                "difficulty_level": DIFFICULTY_LEVEL
            })
            logger.info(f"Question sauvegardée: {qa.question_text}")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la question: {e}")

    return saved_questions

async def fetch_questions_from_document(
    document_id: str,
    conn,
    status_filter: Optional[str] = "generated",
    difficulty_filter: Optional[int] = None,
    theme_filter: Optional[str] = None
) -> List[Dict]:
    """
    Récupère les questions associées à un document depuis la base de données.

    Args:
        document_id (str): ID du document.
        conn (asyncpg.Connection): Connexion à la base de données.
        status_filter (Optional[str]): Filtre par statut.
        difficulty_filter (Optional[int]): Filtre par niveau de difficulté.
        theme_filter (Optional[str]): Filtre par thème.

    Returns:
        List[Dict]: Liste des questions récupérées.
    """
    questions = await get_questions_by_document_id(
        document_id=document_id,
        conn=conn,
        include_answers=True,
        status_filter=status_filter,
        difficulty_filter=difficulty_filter,
        theme_filter=theme_filter
    )
    logger.info(f"Nombre de questions récupérées: {len(questions)}")
    return questions

async def main():

    try:
        chunks = await get_chunks_for_document(document_id=DOCUMENT_ID, conn=await get_db_connection())
        # [(chunkid, chunk_content),...]
        logger.info(f"{len(chunks)}Chunks reçus")
        logger.info("Génération des questions/réponses...")
        for chunk in chunks:
            saved_questions = await generate_and_save_questions(
                document_content=chunk[1],
                chunk_id=chunk[0],
                num_questions=3)
        logger.info(f"Questions générées et sauvegardées: {len(saved_questions)}")

        # 4. Récupérer les questions depuis la base de données
        logger.info("Récupération des questions depuis la base de données...")
        fetched_questions = await fetch_questions_from_document(
            document_id=DOCUMENT_ID,
            conn=await get_db_connection(),
            status_filter="generated",
        )

        # 5. Afficher les résultats
        logger.info("\n=== Questions générées et sauvegardées ===")
        for q in saved_questions:
            logger.info(f"Question: {q['question']}")
            logger.info(f"Réponse: {q['answer']}")
            logger.info(f"Statut: {q['status']}\n")

        logger.info("\n=== Questions récupérées depuis la base de données ===")
        for q in fetched_questions:
            logger.info(f"Question ID: {q['question_id']}")
            logger.info(f"Question: {q['content']}")
            logger.info(f"Statut: {q['status']}")
            logger.info(f"Réponses: {[a['content'] for a in q['answers']]}\n")

    except Exception as e:
        logger.error(f"Erreur lors de l'exécution du script: {e}")


if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
