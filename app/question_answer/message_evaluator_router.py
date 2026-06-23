"""
Router FastAPI pour l'évaluation des messages avec message_evaluator_agent.

Ce router fournit un endpoint pour tester l'agent message_evaluator_agent
sur des réponses utilisateur et enregistrer les résultats avec évaluation manuelle.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

from agents.message_evaluator_agent import (
    get_message_type_agent,
    MessageTypeRequestInput,
    MessageTypeResult,
)
from agents.token_monitor import monitor_agent_call

from .models import EvaluateMessageTypeRequest, MessageEvaluatorResult
from .message_evaluator_logger import log_message_evaluator_result, get_csv_file_path

# Import pour accéder à la BDD
from database.database import get_db_connection, get_question_by_id

router = APIRouter(prefix="/api/admin/message-evaluator", tags=["Admin", "Message Evaluator"])

# Variable pour stocker l'agent (lazy initialization)
_message_evaluator_agent = None


def get_evaluator_agent():
    """Retourne l'agent message_evaluator_agent, en l'initialisant si nécessaire."""
    global _message_evaluator_agent
    if _message_evaluator_agent is None:
        _message_evaluator_agent = get_message_type_agent("ministral-3b-2410")
    return _message_evaluator_agent


@router.post(
    "/evaluate",
    response_model=MessageEvaluatorResult,
    status_code=status.HTTP_200_OK,
    summary="Évalue une réponse avec message_evaluator_agent",
    description="Teste l'agent message_evaluator_agent sur une réponse utilisateur "
                "et enregistre l'évaluation manuelle dans un fichier CSV.",
)
async def evaluate_message_type(request: EvaluateMessageTypeRequest):
    """
    Évalue une réponse avec l'agent message_evaluator_agent.

    L'agent classe la réponse comme : 'reponse', 'hors_sujet', 'demande_renseignement', ou 'autre'.
    La réponse de référence est récupérée depuis la BDD via question_id.
    Les résultats sont sauvegardés dans question_answer/message_evaluator_results.csv.

    Args:
        request: EvaluateMessageTypeRequest avec document_id, question_id, question_text, user_answer, manual_evaluation

    Returns:
        MessageEvaluatorResult avec les résultats de l'agent et confirmation de sauvegarde

    Raises:
        HTTPException: Si l'évaluation échoue
    """
    try:
        # Récupérer la question depuis la BDD pour obtenir la réponse de référence
        conn = await get_db_connection()
        question = await get_question_by_id(conn, request.question_id, include_answers=True)
        
        # Extraire la réponse de référence de manière sécurisée
        reference_answer = question.get("answers", [{}])[0].get("content", "") if question.get("answers") else ""
        
        # Appeler l'agent message_evaluator_agent
        input_data = MessageTypeRequestInput(
            current_question=request.question_text,
            reference_answer=reference_answer,
            user_message=request.user_answer,
        )
        message_evaluator_agent = get_evaluator_agent()
        print("envoi de l'appel")
        # Appel synchrone à l'agent
        result, token_count_result, output_tokens = monitor_agent_call(
            message_evaluator_agent,
            user_input=input_data,
            method="run"
        )
        print(result)
        # Vérifier que le résultat est valide
        if not isinstance(result, MessageTypeResult):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur: le résultat de l'agent n'est pas au bon format"
            )

        # Sauvegarder dans le CSV
        csv_path = log_message_evaluator_result(
            document_id=request.document_id,
            question_id=request.question_id,
            question_text=request.question_text,
            reference_answer=reference_answer,
            user_answer=request.user_answer,
            agent_message_type=result.message_type,
            agent_confidence=result.confidence,
            agent_explanation=result.explanation,
            manual_evaluation=request.manual_evaluation,
        )

        return MessageEvaluatorResult(
            agent_message_type=result.message_type,
            agent_confidence=result.confidence,
            agent_explanation=result.explanation,
            manual_evaluation=request.manual_evaluation,
            saved_to_csv=True,
            csv_file_path=csv_path,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'évaluation: {str(e)}"
        )


@router.get(
    "/csv-path",
    summary="Récupère le chemin du fichier CSV",
    description="Retourne le chemin du fichier CSV contenant les résultats des évaluations.",
)
async def get_csv_path_endpoint():
    """
    Retourne le chemin du fichier CSV des évaluations.

    Returns:
        JSON avec le chemin du fichier CSV
    """
    csv_path = get_csv_file_path()
    return JSONResponse(
        content={
            "csv_file_path": csv_path,
            "exists": os.path.exists(csv_path),
        }
    )


# Fix import issue
import os
