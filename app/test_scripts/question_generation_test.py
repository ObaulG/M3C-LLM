import asyncio

import logging
from typing import List, Dict, Optional

import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from agents.qa_agent import get_qa_agent, QuestionRequestInput, QuestionAnswerList, QuestionAnswer
from database import get_db_connection, save_question_to_db, get_chunk_by_id, get_questions_by_document_id, get_chunks_for_document

# Constantes
DOCUMENT_ID = "8a672d2ae6f2abfa4434e0f4145a9aa77bbc6d56"
DIFFICULTY_LEVEL = 3

models_evaluator = ["ministral-3b-latest",
                    "ministral-8b-latest",
                    "mistral-small-latest",
                    "mistral-medium-latest",
                    "mistral-large-latest"]

async def generate_questions_on_chunk_multiple_models(
    document_content: str,
    num_questions: int = 3):

    # 1. Initialiser l'agent de génération de questions
    qa_agents = [get_qa_agent(model=model) for model in models_evaluator]

    # 2. Générer les questions/réponses
    input_schema = QuestionRequestInput(
        message=f"Génère {num_questions} questions diversifiées sur le document.",
        document=document_content
    )
    print("schema")
    tasks = [asyncio.to_thread(agent.run, input_schema) for agent in qa_agents]
    print("tasks")
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    print("responses")

    return responses

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


async def generate_and_save_questions_multiple_models(
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
    qa_agents = [get_qa_agent(model=model) for model in models_evaluator]

    # 2. Générer les questions/réponses
    input_schema = QuestionRequestInput(
        message=f"Génère {num_questions} questions diversifiées sur le document.",
        document=document_content
    )
    print("schema")
    tasks = [asyncio.to_thread(agent.run,input_schema) for agent in qa_agents]
    print("tasks")
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    print("responses")
    # 3. Sauvegarder les questions/réponses en base de données
    saved_questions = []
    for i, response in enumerate(responses):
        if not isinstance(response, QuestionAnswerList):
            continue

        for qa in response.questions_answers:
            try:
                await save_question_to_db(
                    question=qa.question_text,
                    answer=qa.answer_text,
                    chunk_id=chunk_id,
                    conn=await get_db_connection(),
                    difficulty_level=DIFFICULTY_LEVEL,
                    model=models_evaluator[i],
                )
                saved_questions.append({
                    "question": qa.question_text,
                    "answer": qa.answer_text,
                    "status": "generated",
                    "difficulty_level": DIFFICULTY_LEVEL,
                    "model": models_evaluator[i],
                })
                logger.info(f"Question sauvegardée: [{models_evaluator[i]}] {qa.question_text}")
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

async def generate_and_save_questions_entire_document(document_id=DOCUMENT_ID,
                                                      nb_questions=3,
                                                      chunking_strategy_id=7):
    try:
        chunks = await get_chunks_for_document(document_id=DOCUMENT_ID,
                                               conn=await get_db_connection(),
                                               chunking_strategy_id=chunking_strategy_id)
        # [(chunkid, chunk_content),...]
        logger.info(f"{len(chunks)}Chunks reçus")
        logger.info("Génération des questions/réponses...")
        for chunk in chunks:
            saved_questions = await generate_and_save_questions_multiple_models(
                document_content=chunk[1],
                chunk_id=chunk[0],
                num_questions=nb_questions)
        logger.info(f"Questions générées et sauvegardées: {len(saved_questions)}")

        # 5. Afficher les résultats
        logger.info("\n=== Questions générées et sauvegardées ===")
        for q in saved_questions:
            logger.info(f"Question: {q['question']}")
            logger.info(f"Réponse: {q['answer']}")
            logger.info(f"Statut: {q['status']}\n")

    except Exception as e:
        logger.error(f"Erreur lors de l'exécution du script: {e}")

async def main(document_ids: list[str],
               nb_questions: int = 3,
               chunking_strategy_id: int = 7,):

    for doc_id in document_ids:
        await generate_and_save_questions_entire_document(document_id=doc_id,
                                                    nb_questions=nb_questions,
                                                    chunking_strategy_id=chunking_strategy_id)


async def test_no_save():
    chunks = await get_chunks_for_document(document_id=DOCUMENT_ID,
                                           conn=await get_db_connection(),
                                           chunking_strategy_id=7)
    chunk_id_test = "8a672d2ae6f2abfa4434e0f4145a9aa77bbc6d56-7-14"
    document_id_test = "8a672d2ae6f2abfa4434e0f4145a9aa77bbc6d56"

    chunk = await get_chunk_by_id(chunk_id_test, await get_db_connection())

    responses = await generate_questions_on_chunk_multiple_models(
        document_content=chunk["content"],
        num_questions=3)

    print(responses)
    data = []
    for i, response in enumerate(responses):
        # response est un QuestionAnswerList
        print(type(response))
        if not isinstance(response, QuestionAnswerList):
            continue
        print("adding new questions")
        for qa in response.questions_answers:
            if not isinstance(response, QuestionAnswer):
                continue
            # qa est un QuestionAnswer
            data.append({
                "model": models_evaluator[i],
                "question": qa.question_text,
                "answer": qa.answer_text,
            })

    data_for_pandas = {"model": [d["model"] for d in data],
                       "question": [d["question"] for d in data],
                       "answer": [d["answer"] for d in data]}
    # 4. Créer un DataFrame et exporter en CSV
    df = pd.DataFrame.from_dict(data, orient="index")
    filename = f"questions_reponses_chunk_{chunk_id_test}.csv"
    df.to_csv(filename, index=False, encoding="utf-8")

    print(f"Export terminé : {filename}")


if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    document_ids = ["8a672d2ae6f2abfa4434e0f4145a9aa77bbc6d56",
                    "dbd5f14a9e6545880b0cd505583ea7d1fe1e8b3d",
                    "2f11a893316ef707028b1389f9dfbae717ea4f4e"]
    asyncio.run(main(document_ids,
                     nb_questions=3,
                     chunking_strategy_id=7))
