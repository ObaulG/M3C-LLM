"""
Module d'évaluation de réponse à une question, hors contexte de session.

Ce module permet d'évaluer une réponse utilisateur à une question donnée,
en réutilisant les agents message_evaluator_agent et answer_evaluator_agent.
Les étapes d'évaluation sont découpées en plusieurs fonctions pour une meilleure
modularité et maintenabilité.
"""

import asyncio
import time
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from pydantic import BaseModel, Field

# Imports pour la base de données
from app.database.database import get_db_connection, get_question_by_id

# Imports pour les agents
from app.agents.message_evaluator_agent import (
    get_message_type_agent,
    MessageTypeRequestInput,
    MessageTypeResult
)
from app.agents.answer_evaluator_agent import (
    get_evaluator_agent,
    get_final_evaluator_agent,
    EvaluateRequestInput,
    AgentEvaluationResult,
    ListAgentEvaluationResult
)

from .csv_logger import log_response_to_csv
# Imports pour le monitoring des tokens
from app.agents.token_monitor import monitor_agent_call, monitor_agent_call_async

class QuestionAnswer(BaseModel):
    """Représente une paire question-réponse.

    Cette classe modélise une question et sa réponse associée.

    Attributes:
        question_text (str): Le texte de la question posée.
        answer_text (str): Le texte de la réponse correspondante.
    """
    question_text: str
    answer_text: str

class QuestionAnswerList(BaseModel):
    questions_answers: List[QuestionAnswer]

class EvaluationResult(BaseModel):
    """
    Représente le résultat de l'évaluation d'une réponse par un modèle de langage.
    Utilisé dans UserEvaluationResponse qui référence l'id de la question et son texte.
    """
    score: int
    feedback: str
    model: Optional[str]
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0

class UserEvaluationResponse(BaseModel):
    """
    Représente les données d'une réponse donnée à une question par un utilisateur.
    Si l'évaluation n'a pas été faite, alors elle n'est pas renseignée.
    """
    question_id: int
    question_text: str
    user_answer: str
    date_sent: datetime
    evaluation: Optional[EvaluationResult]
    individual_evaluations: Optional[List[EvaluationResult]] = None
    message_type: Optional[str] = None  # "réponse", "demande_renseignement", "hors_sujet", "autre"
    metadata: Optional[Dict] = None


def from_AgentEvaluationResult_to_EvaluationResult(evaluation: AgentEvaluationResult,
                                                   model: Optional[str] = None,
                                                   input_tokens: Optional[int] = 0,
                                                   output_tokens :Optional[int] = 0) -> EvaluationResult:
    return EvaluationResult(
        score= evaluation.score,
        feedback=evaluation.feedback,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens
    )


async def _determine_message_type(
    question_text: str,
    reference_answers: List[str],
    user_answer: str
) -> Tuple[str, float, str, int, int]:
    message_ev_agent = get_message_type_agent()
    
    if message_ev_agent is None:
        raise RuntimeError("L'agent message_evaluator n'est pas initialisé. Appeler init_evaluators() au préalable.")
    
    # Préparer l'entrée pour l'agent (même structure que dans message_evaluator_router.py)
    input_data = MessageTypeRequestInput(
        current_question=question_text,
        reference_answers=reference_answers,
        user_message=user_answer
    )
    
    # Appel à l'agent avec monitoring des tokens (comme dans api_server.py)
    result, token_count_result, output_tokens = monitor_agent_call(
        message_ev_agent,
        user_input=input_data,
        method="run"
    )
    
    # Vérifier que le résultat est valide
    if not isinstance(result, MessageTypeResult):
        raise RuntimeError(
            f"Le résultat de l'agent n'est pas au bon format. Type obtenu: {type(result)}"
        )
    
    return (
        result.message_type,
        result.confidence,
        result.explanation,
        token_count_result,
        output_tokens
    )



async def _evaluate_answer_single_model(question_id: int,
                                        question_text: str,
                                        answer: str ,
                                        reference_answers: list[str],
                                        model: str,
                                        logging_csv: bool = True) -> EvaluationResult:

    evaluation_input = EvaluateRequestInput(
        question=question_text,
        expected_answers=reference_answers,
        user_answer=answer
    )

    provider, model_name = tuple(model.split("/"))
    evaluator = get_evaluator_agent(model_name, provider=provider, async_mode=True)
    start_time = time.time()
    result, input_tokens, output_tokens = await monitor_agent_call_async(evaluator, evaluation_input, "run_async")
    end_time = time.time()
    time_elapsed = end_time - start_time
    evaluation_result = from_AgentEvaluationResult_to_EvaluationResult(result, input_tokens, output_tokens)

    if logging_csv:
        log_response_to_csv(evaluation_input, evaluation_result, question_id, time_elapsed)
    return evaluation_result

async def _aggregate_evaluations(evaluations: List[EvaluationResult], csv_logging:bool = True) -> EvaluationResult:
    # 1. Convertir chaque EvaluationResult en AgentEvaluationResult
    agent_evaluations = [
        AgentEvaluationResult(score=ev.score, feedback=ev.feedback)
        for ev in evaluations
    ]

    # 2. Créer ListAgentEvaluationResult
    list_agent_evaluation = ListAgentEvaluationResult(evaluations=agent_evaluations)

    # 3. Obtenir l'agent final avec paramètres par défaut
    final_evaluator = get_final_evaluator_agent(async_mode=True)

    # 4. Appeler l'agent avec monitoring des tokens
    result, input_tokens, output_tokens = await monitor_agent_call_async(
        final_evaluator,
        list_agent_evaluation,
        "run_async"
    )

    # 5. Convertir et retourner le résultat
    return from_AgentEvaluationResult_to_EvaluationResult(
        result,
        model="final_evaluator",
        input_tokens=input_tokens,
        output_tokens=output_tokens
    )
# ============================================================================
# Fonction principale
# ============================================================================

async def evaluate_answer(
    question_id: int,
    user_answer: str,
    evaluator_models: list[str],
    evaluator_final: Optional[str],
    csv_logging: bool = True,
    num_reference_answers: Optional[list[int]] = None
) -> UserEvaluationResponse:

    #1. récupérer la question et les réponses
    question = await get_question_by_id(await get_db_connection(),
                                        question_id,
                                        include_answers=True)
    # vérifier que les réponses existent
    all_reference_answers = [answer["content"] for answer in question["answers"]]

    if num_reference_answers is None:
        reference_answers = all_reference_answers
    elif num_reference_answers >= 1:
        # Utiliser un nombre spécifique de réponses (les n premières)
        # Si n > len(all_reference_answers), prend toutes les réponses disponibles
        reference_answers = all_reference_answers[:num_reference_answers]
    else:
        raise ValueError("num_reference_answers doit être None ou un entier positif")
    
    # Initialiser les compteurs de tokens
    total_input_tokens = 0
    total_output_tokens = 0

    evaluations = []
    for model in evaluator_models:
        evaluation = await _evaluate_answer_single_model(question_id,
                                                          question["content"],
                                                          user_answer,
                                                          reference_answers,
                                                          model,
                                                          csv_logging)
        evaluations.append(evaluation)
        total_input_tokens += evaluation.input_tokens
        total_output_tokens += evaluation.output_tokens

    final_evaluation = None
    if evaluator_final:
        final_evaluation = await _aggregate_evaluations(evaluations)
        total_input_tokens += final_evaluation.input_tokens
        total_output_tokens += final_evaluation.output_tokens


    
    # Construire et retourner le résultat final
    return UserEvaluationResponse(
        question_id=question_id,
        question_text=question["content"],
        user_answer=user_answer,
        message_type="reponse",
        evaluation=final_evaluation,
        individual_evaluations=evaluations,
        metadata={ "token_usage":{
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens
        }}
    )
