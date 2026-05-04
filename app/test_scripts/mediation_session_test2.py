import asyncio
import logging
from database.database import (get_db_connection,
                      get_questions_by_document_id,
                      get_question_by_id,
                      get_chunks_by_question_id,
                      delete_questions_for_pages_1_to_12)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

models_evaluator = ["ministral-3b-latest",
                    "ministral-8b-latest",
                    "mistral-small-latest",
                    "mistral-medium-latest",
                    "mistral-large-2411",
                    "mistral-large-latest"
                    ]
# Import des agents
from agents.answer_evaluator_agent import EvaluateRequestInput, get_evaluator_agent


async def simulate_cultural_mediation_session(
    document_id: str,
    num_questions: int = 5,
    min_score_threshold: int = 7
) -> None:
    """
    Simule une session de médiation culturelle en posant des questions à l'utilisateur
    et en évaluant ses réponses, avec affichage des pages correspondantes.
    """
    try:
        logger.info(f"Sélection de {num_questions} questions pour le document: {document_id}")

        # Récupérer les questions depuis la base de données
        conn = await get_db_connection()
        #questions = await get_questions_by_document_id(
        #    document_id=document_id,
        #    conn=conn,
        #    include_answers=True,
        #    nb_limit=num_questions
        #)
        # old values
        #questions_ids = [370, 364, 519, 786, 115]
        questions_ids = [370, 364, 519, 786, 115]
        questions = [await get_question_by_id(conn, id) for id in questions_ids]
        if not questions:
            logger.warning(f"Aucune question trouvée pour le document {document_id}.")
            return
        logger.info("Questions récupérées")
        print(questions)
        # evaluator = get_evaluator_agent()
        evaluators = [get_evaluator_agent(model) for model in models_evaluator]
        correct_answers = 0

        for i, question in enumerate(questions, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Question {i}/{num_questions}: {question.get('content', 'N/A')}")
            logger.info(f"Thème: {question.get('theme', 'N/A')}")
            logger.info(f"Niveau de difficulté: {question.get('difficulty_level', 'N/A')}")

            # Récupérer les chunks associés à cette question
            chunks = await get_chunks_by_question_id(question['question_id'], conn)
            print(chunks)
            # Afficher les pages correspondantes
            pages = set()
            for chunk in chunks:
                pages.add(chunk['num_page'])

            logger.info(f"Pages correspondantes dans le document: {', '.join(map(str, pages))}")

            for chunk in chunks:
                logger.info(f"\nExtrait de la page {chunk['num_page']} (position {chunk['position_in_page']}):")

            # Demander la réponse de l'utilisateur
            user_answer = input("Votre réponse: ").strip()

            # Évaluer la réponse
            expected_answer = question['answers'][0]['content'] if question.get('answers') else "Réponse non disponible"
            evaluation_input = EvaluateRequestInput(
                question=question['content'],
                expected_answer=expected_answer,
                user_answer=user_answer
            )

            evaluations = []
            for evaluator in evaluators:
                evaluation = evaluator.run(evaluation_input)
                evaluations.append(evaluation)
                logger.info(f"\nScore: {evaluation.score}/10")
                logger.info(f"Feedback: {evaluation.feedback}")

            score = sum([evaluation.score for evaluation in evaluations]) / len(evaluators)
            print(f"Score agrégé: {score}")
            if score >= min_score_threshold:
                correct_answers += 1

        # Fermer la connexion
        await conn.close()

        # Résumé de la session
        logger.info(f"\n{'='*60}")
        logger.info(f"Session terminée. Vous avez répondu correctement à {correct_answers}/{num_questions} questions.")
        if correct_answers >= num_questions * 0.7:
            logger.info("Félicitations ! Vous avez réussi la médiation pour ce document.")
        else:
            logger.info("Vous n'avez pas atteint le seuil requis. Vous pouvez réessayer plus tard.")

    except Exception as e:
        logger.error(f"Erreur lors de la session: {e}")


async def main():
    """
    Fonction principale pour exécuter le script de test.
    """
    try:
        document_id = "dbd5f14a9e6545880b0cd505583ea7d1fe1e8b3d.pdf"
        conn = await get_db_connection()
        await conn.commit()
        await simulate_cultural_mediation_session(document_id, num_questions=5)
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution du script: {e}")

if __name__ == "__main__":
    # Configuration pour Windows (nécessaire pour asyncio sur Windows)
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
