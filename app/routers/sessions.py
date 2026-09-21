"""Router FastAPI pour les sessions (questions et RAG).

Regroupe les routes /api/sessions/* : initialisation et messages d'une
session de questions/réponses, création et consultation de sessions RAG,
exports CSV. Ces routes étaient auparavant définies dans api_server.py.
"""
import asyncio
import csv
import json
import logging
import math
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from question_session import (
    PREMADE_QUESTIONS_BY_DOCUMENT_ID,
    QuestionSessionManager,
    SessionStatus,
    session_status_to_dict,
)
from rag_session import RAGSessionManager, RAGSession
from question_answer.answer_evaluation import (
    UserEvaluationResponse,
    from_AgentEvaluationResult_to_EvaluationResult,
)
from agents.answer_evaluator_agent import EvaluateRequestInput
from session_csv_logger import log_response_to_csv
from agents.message_evaluator_agent import MessageTypeRequestInput
from agents.token_monitor import monitor_agent_call, monitor_agent_call_async
from database.database import (
    get_db_connection,
    get_questions_by_ids,
    get_question_by_id,
    get_chunks_by_question_ids,
    insert_session,
)

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])

# modèles et providers des agents évaluateurs ; l'ordre est important :
# models_evaluator[i] correspond à app.state.evaluators[i]
models_evaluator = [("ministral-8b-latest", "mistral"),
                    ("ministral-14b-2512", "mistral"),
                    ("ministral-3b-latest", "mistral")]

question_session_manager = QuestionSessionManager()
rag_session_manager = RAGSessionManager()


class QuestionSessionMessage(BaseModel):
    session_id: str
    user_message: str


class QuestionSessionResponse(BaseModel):
    session_status: SessionStatus
    computed_message_type: str
    # TODO: utiliser une structure pour indiquer les données de consommation
    #       en tokens. Prévoir également un type générique.
    metadata: dict
    total_time: float
    message: str
    # pour faciliter le traitement côté client
    new_question: bool
    is_finished: bool


def _get_evaluators(request: Request):
    evaluators = getattr(request.app.state, "evaluators", [])
    if not evaluators:
        logging.error("Évaluateurs non initialisés")
        raise HTTPException(status_code=500, detail="Évaluateurs non initialisés")
    return evaluators


def _get_message_ev_agent(request: Request):
    agent = getattr(request.app.state, "message_ev_agent", None)
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent de type de message non initialisé")
    return agent


def _append_session_to_json(session_dict, file_path: str = "sessions_backup.json"):
    file = Path(file_path)
    sessions_data = []
    if file.exists():
        with open(file, "r", encoding="utf-8") as f:
            try:
                sessions_data = json.load(f)
            except json.JSONDecodeError:
                sessions_data = []
    sessions_data.append(session_dict)
    with open(file, "w", encoding="utf-8") as f:
        json.dump(sessions_data, f, indent=2, ensure_ascii=False)


def persist_sessions_on_shutdown(app):
    """Sauvegarde les sessions questions dans sessions_backup.json (appel au shutdown)."""
    for session_id in question_session_manager.sessions:
        s = question_session_manager.get_session_status(session_id)
        session_dict = session_status_to_dict(s)
        session_dict["metadata"] = {
            "llm_used": "mistral-7b",
            "number_of_agents": 3,
            "server_shutdown_at": datetime.now().isoformat(),
        }
        _append_session_to_json(session_dict)



@router.post("/questions/init/{document_id}", response_model=SessionStatus)
async def init_question_session(document_id: int,
                                premade_session: bool = True):
    """
    Initialise une nouvelle session de questions/réponses pour un document donné.
    Retourne l'ID de la session et les questions générées.
    """
    document_id = int(document_id)
    session_id = question_session_manager.create_session(document_id, premade_session)
    if not premade_session:
        # TODO: pour plus tard, en récupérant l'historique de l'utilisateur
        #       et éventuellement ses préférences. Suite de questions recommandées
        #       par LLM, IA plus classique, ou bien créée et corrigée par des utilisateurs
        #       experts ou vérifiés.
        raise NotImplementedError
    async with await get_db_connection() as conn:
        await insert_session(conn,
                                session_id,
                                None,
                                document_id,
                                datetime.now().isoformat())
    
    # on détermine les questions qui seront posées. La sélection est faite à l'avance.
    questions_ids = PREMADE_QUESTIONS_BY_DOCUMENT_ID[int(document_id)]
    async with await get_db_connection() as conn:
        questions = await get_questions_by_ids(questions_ids, conn)

        print(questions)
    # note: il y a une liste par question, car une question peut avoir plusieurs chunks
    # TODO: il faudra ajouter avec le document la méthode de chunking utilisée,
    #       car pour le même document, il peut être découpé de plusieurs maniÃ¨res, donc avoir
    #       plusieurs chunks pour la même question.
        questions_chunks = await get_chunks_by_question_ids(questions_ids, conn)
    questions_texts = [question["content"] for question in questions]
    question_pages = [chunk[0]["num_page"] for chunk in questions_chunks]

    question_session_manager.add_questions(session_id, questions_ids, questions_texts, question_pages)
    return question_session_manager.get_session_status(session_id)


@router.post("/questions/message", response_model=QuestionSessionResponse)
async def submit_question_session_message(request: QuestionSessionMessage, http_request: Request):
    """
    Ajoute un message à la conversation d'une session. L'agent analyse la réponse pour vérifier
    si c'est la réponse à la question en cours, ou une demande de contexte supplémentaire.
    """

    # TODO: fonction trop longue, à découper

    start_time = time.time()
    total_input_tokens = 0
    total_output_tokens = 0
    session_id = request.session_id
    user_message = request.user_message
    session = question_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    evaluators = getattr(app.state, "evaluators", [])
    if not evaluators:
        logging.error("Evaluateurs non initialisés")
        raise HTTPException(status_code=500, detail="Evaluateurs non initialisés")
    current_question_id = question_session_manager.get_current_question_id(session_id)
    if not current_question_id:
        raise HTTPException(status_code=500, detail="Erreur détectée lors du traitement de la session")
    # récupérer la question et ses réponses
    question = await get_question_by_id(await get_db_connection(),
                                        current_question_id,
                                        include_answers=True)
    # vérifier que les réponses existent
    reference_answers = [answer["content"] for answer in question["answers"]]
    # vérification du type de message.
    # -> Tuple[OutputSchema, int, int]
    message_ev_agent = getattr(app.state, "message_ev_agent", None)
    if message_ev_agent is None:
        raise HTTPException(status_code=500, detail="Agent de type de message non initialis\u00e9")
    result, token_count_result, output_tokens = monitor_agent_call(message_ev_agent,
                                                                   user_input=MessageTypeRequestInput(
                                                                              current_question=question["content"],
                                                                              reference_answers=reference_answers,
                                                                              user_message=user_message
                                                                   ),
                                                                   method = "run")
    message_type = result.message_type
    total_input_tokens += token_count_result
    total_output_tokens += output_tokens
    logging.info("Message type determined : {message_type}".format(message_type=message_type),)
    new_question = False
    is_finished = False
    message = ""
    user_response = UserEvaluationResponse(
        question_id=current_question_id,
        question_text=question['content'],
        user_answer=user_message,
        date_sent=datetime.now(),
        evaluation=None,
        message_type=message_type
    )
    match message_type:
        case "reponse":
            if not question["answers"]:
                raise HTTPException(status_code=500, detail="Pas de réponse prévue pour cette question...")
            # Utiliser toutes les réponses disponibles pour l'évaluation
            expected_answers = [answer["content"] for answer in question["answers"]]
            evaluation_input = EvaluateRequestInput(
                question=question['content'],
                expected_answers=expected_answers,
                user_answer=user_message
            )
            # note: les evaluators sont initialisés avec des clients async.
            # pour pouvoir effectuer ces appels en parallèle.
            evaluations = []


            # lancement des évaluations pour chaque evaluator
            coroutines = [
                monitor_agent_call_async(evaluator, evaluation_input, "run_async")
                for evaluator in evaluators
            ]
            eval_results = await asyncio.gather(*coroutines)
            for result in eval_results:
                evaluation, token_count_result, output_tokens = result
                evaluations.append(evaluation)
                total_input_tokens += token_count_result
                total_output_tokens += output_tokens

            """    
            if len(evaluations) > 1:
                # /!\ contient un AgentEvaluationResult de answer_evaluation_agent.py.
                # UserEvaluationResponse attend pour l'attribut evaluation un EvaluationResult de
                # question_session.py
                # Provoque souvent cette erreur, pk ?
                # Instructor does not support multiple tool calls, use List[Model] instead
                final_evaluation, token_count_result, output_tokens = monitor_agent_call(final_evaluator,
                                                            ListAgentEvaluationResult(
                                                                evaluations=evaluations),
                                                            "run")
                total_input_tokens += token_count_result
                total_output_tokens += output_tokens
            else:
                final_evaluation = evaluations[0]
            """

            # Stocker les évaluations individuelles avec leurs modèles
            individual_evaluations = []
            total_score = 0
            for i, eval_result in enumerate(evaluations):
                # Le modèle de chaque évaluateur correspond à models_evaluator[i][0]
                eval_model = models_evaluator[i][0] if i < len(models_evaluator) else f"evaluator_{i}"
                individual_eval = from_AgentEvaluationResult_to_EvaluationResult(
                    eval_result, model=eval_model
                )
                total_score += individual_eval.score
                individual_evaluations.append(individual_eval)
            user_response.individual_evaluations = individual_evaluations

            # à partir des évaluations individuelles, on calcule la note qui sera attribuée
            evaluation_final_result = math.ceil(total_score / len(models_evaluator))
            user_response.evaluation = evaluation_result
            if evaluation_result.score >= 7:
                # Si le score est suffisant, passer à la question suivante
                # peut également marquer la fin de la session si c'était la dernière qst
                question_session_manager.increment_current_index(session_id)
                is_finished = question_session_manager.is_finished(session_id)
                if not is_finished:
                    new_question = True
            # le client pourra détécter les changements par rapport à l'ancienne version de
            # sessionStatus : chgt de question, question à refaire, ou fin de session
            message = evaluation_result.feedback
        case "demande_renseignement":
            # faire appel à un LLM pour répondre à la question
            message = "Message de demande de renseignement détecté (pas implémenté pour l'instant)"
            pass
        case "hors_sujet":
            message = "Message hors-sujet détecté (pas implémenté pour l'instant)"
            pass
        case "autre":
            message = "Message classé hors-catégorie..."
            pass
    total_time = time.time() - start_time
    print("user response: ", user_response)
    # mettre à jour la session
    question_session_manager.add_response(session_id, user_response)
    print("session updated:")
    print(question_session_manager.get_session(session_id))
    # Log la réponse dans le CSV pour évaluation humaine
    log_response_to_csv(session_id, user_response)
    # Sauvegarder dans la base SQL
    session_response = QuestionSessionResponse(
        session_status=question_session_manager.get_session_status(session_id),
        computed_message_type=message_type,
        message=message,
        new_question=new_question,
        is_finished=is_finished,
        total_time=total_time,
        # note: le format de token_usage se calque sur celui de LangChain
        #       le JS fonctionne sur ce format (pour l'instant)
        # TODO: il sera à modifier plus tard.
        metadata={"token_usage":{
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,}}
    )
    return session_response


@router.get("/rag/init/{document_id}")
async def create_rag_session(document_id: str) -> dict:
    """
    Créée un session_id de RAG retourné à l'utilisateur
    """
    session_id = rag_session_manager.create_session(document_id)
    print("session created : ", session_id)
    return {"session_id": session_id}
@router.get("/rag/{rag_session_id}")
async def get_rag_session(rag_session_id: str) -> RAGSession:
    """
    RécupÃ¨re l'état actuel d'une RAGSession.
    """
    print("retrieving session: ", rag_session_id)
    session = rag_session_manager.get_session(rag_session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session RAG introuvable")
    return session


@router.get("/questions/export/{session_id}")
async def export_question_session(session_id: str):
    """
    Exporte les réponses d'une session au format CSV.
    """
    session = question_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    # Générer le nom du fichier CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"session_{session_id}_{timestamp}.csv"
    filepath = os.path.join("exports", filename)
    # Créer le dossier "exports" s'il n'existe pas
    os.makedirs("exports", exist_ok=True)
    # Ã‰crire le CSV
    with open(filepath, mode="w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "date_sent",
            "question_text",
            "user_answer",
            "question_id",
            "message_type",
            "score",
            "feedback",
            "model",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        prev_question = None
        for response in session["responses"]:
            row = {
                "date_sent": response.date_sent.isoformat() if hasattr(response, "date_sent") and response.date_sent else "",
                "question_text": response.question_text if hasattr(response, "question_text") else "",
                "user_answer": response.user_answer if hasattr(response, "user_answer") else "",
                "question_id": response.question_id if hasattr(response, "question_id") else "",
                "message_type": response.message_type if hasattr(response, "message_type") else "",
                "score": response.evaluation.score if hasattr(response, "evaluation") and response.evaluation and hasattr(response.evaluation, "score") else "",
                "feedback": response.evaluation.feedback if hasattr(response, "evaluation") and response.evaluation and hasattr(response.evaluation, "feedback") else "",
                "model": response.evaluation.model if hasattr(response, "evaluation") and response.evaluation and hasattr(response.evaluation, "model") else "",
            }
            if row["question_text"] == prev_question:
                row["question_text"] = ""
            else:
                prev_question = row["question_text"]
            writer.writerow(row)
    return FileResponse(filepath, media_type="text/csv", filename=filename)


@router.get("/questions/{session_id}")
async def get_question_session(session_id: str):
    """
    Récupère une session de questions/réponses par son ID.
    
    Args:
        session_id: Identifiant de la session
    
    Returns:
        SessionStatus: L'état complet de la session avec toutes les réponses
    """
    try:
        session = question_session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session non trouvée")
        return session
    except Exception as e:
        print(f"Erreur lors de la récupération de la session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur: {str(e)}"
        )


@router.get("/rag/export/{session_id}")
async def export_rag_session(session_id: str):
    # writes the csv
    file_path = "rag_sessions_csv/{session_id}.csv".format(session_id=session_id)
    print("creating file at", file_path)
    success = rag_session_manager.export_session_to_csv(session_id)
    if not success:
        raise HTTPException(status_code=500, detail="Erreur lors de la création du fichier CSV. Veuillez réessayer plus tard.")
    return FileResponse(file_path, media_type="text/csv", filename=file_path)
