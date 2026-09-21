"""Router FastAPI pour les évaluations.

Regroupe les routes d'évaluation de réponses (/api/evaluate), les
réponses de référence (/api/reference-answers) et la sauvegarde des
évaluations et feedbacks (/api/evaluations/save, /api/evaluation-feedback/save).
Ces routes étaient auparavant définies dans api_server.py.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from evaluation_logger import log_evaluation_to_csv, get_reference_answers, get_reference_answer
from evaluation_feedback_logger import log_feedback_to_csv
from agents.answer_evaluator_agent import get_evaluator_agent, EvaluateRequestInput

router = APIRouter(tags=["Evaluation"])


@router.post("/api/evaluate", tags=["Evaluation"])
async def evaluate_answer(request: EvaluateRequestInput):
    """
    Évalue une réponse utilisateur par rapport à des réponses attendues.
    Utilise l'agent évaluateur avec le modèle spécifié ou par défaut.
    
    Args:
        request: EvaluateRequestInput avec question, expected_answers, user_answer, model
        model est au format <provider>/<model_name>
    
    Returns:
        AgentEvaluationResult avec score (1-10) et feedback
    """
    try:
        print(f"[{datetime.now().isoformat()}] Évaluation de réponse demandée avec modèle: {request.model}")
        
        # Utiliser le modèle spécifié ou le modèle par défaut
        provider, model = tuple(request.model.split("/")) if request.model else ("mistral", "mistral-small")
        # Créer un agent avec le modèle spécifié
        evaluator = get_evaluator_agent(model, provider=provider, async_mode=True)
        evaluation = await evaluator.run_async(request)
        print(f"[{datetime.now().isoformat()}] Évaluation terminée: score={evaluation.score}")
        return evaluation
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR lors de l'évaluation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'évaluation: {str(e)}"
        )


@router.get("/api/reference-answers", tags=["Evaluation"])
async def get_all_reference_answers():
    """
    Récupère toutes les paires question/réponse de référence depuis le CSV.
    
    Returns:
        Dictionnaire avec question_id comme clé et {answer_id, question_content, response_answer} comme valeur
    """
    try:
        reference_data = get_reference_answers()
        return {"reference_answers": reference_data, "count": len(reference_data)}
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR lors du chargement des réponses de référence: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement des réponses de référence: {str(e)}"
        )


@router.get("/api/reference-answers/{question_id}", tags=["Evaluation"])
async def get_reference_answer_by_id(question_id: int):
    """
    Récupère la réponse de référence pour une question spécifique.
    
    Args:
        question_id: ID de la question
    
    Returns:
        Dictionnaire avec answer_id, question_content, response_answer
    """
    try:
        reference_answer = get_reference_answer(question_id)
        if reference_answer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Aucune réponse de référence trouvée pour la question {question_id}"
            )
        return reference_answer
    except HTTPException:
        raise
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur: {str(e)}"
        )


class EvaluationSaveRequest(BaseModel):
    """Modèle de requête pour sauvegarder une évaluation"""
    question_id: int = Field(..., description="ID de la question")
    answer_id: Optional[str] = Field(None, description="ID de la réponse de référence")
    evaluated_answer: str = Field(..., description="Réponse qui a été évaluée")
    score: Optional[int] = Field(None, description="Note (1-10)", ge=1, le=10)
    feedback: str = Field(..., description="Commentaire sur l'évaluation")
    evaluation_type: str = Field("auto", description="Type d'évaluation: 'auto' ou 'manual'")
    evaluation_source: Optional[str] = Field(None, description="Source de la réponse évaluée: 'llm' ou 'user'")
    model_used: Optional[str] = Field(None, description="Modèle utilisé pour l'évaluation automatique")
    question_content: Optional[str] = Field(None, description="Contenu de la question")
    reference_answer: Optional[str] = Field(None, description="Réponse de référence")


class EvaluationFeedbackRequest(BaseModel):
    """Modèle de requête pour sauvegarder un feedback humain sur une évaluation IA"""
    question_id: int = Field(..., description="ID de la question")
    chunk_id: Optional[str] = Field(None, description="ID du chunk associé")
    question_content: Optional[str] = Field(None, description="Contenu de la question")
    user_answer: str = Field(..., description="Réponse qui a été évaluée")
    ai_score: int = Field(..., description="Note générée par l'IA", ge=1, le=10)
    ai_feedback: str = Field(..., description="Commentaire généré par l'IA")
    human_rating: int = Field(..., description="Note humaine sur l'évaluation IA (1-10)", ge=1, le=10)
    human_comment: Optional[str] = Field(None, description="Commentaire humain sur l'évaluation IA")


@router.post("/api/evaluations/save", tags=["Evaluation"])
async def save_evaluation(request: EvaluationSaveRequest):
    """
    Sauvegarde une évaluation dans le fichier question-answer-reference-eval.csv.
    
    Args:
        request: EvaluationSaveRequest avec toutes les données d'évaluation
    
    Returns:
        Message de confirmation avec le chemin du fichier
    """
    try:
        evaluation_data = request.model_dump()
        filepath = log_evaluation_to_csv(evaluation_data)
        print(f"[{datetime.now().isoformat()}] Évaluation sauvegardée dans {filepath}")
        return {
            "message": "Évaluation sauvegardée avec succès",
            "filepath": filepath,
            "evaluation_id": f"{request.question_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR lors de la sauvegarde: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la sauvegarde: {str(e)}"
        )


@router.post("/api/evaluation-feedback/save", tags=["Evaluation"])
async def save_evaluation_feedback(request: EvaluationFeedbackRequest):
    """
    Sauvegarde un feedback humain sur une évaluation IA dans le fichier evaluation-feedback.csv.
    
    Args:
        request: EvaluationFeedbackRequest avec toutes les données de feedback
    
    Returns:
        Message de confirmation avec le chemin du fichier
    """
    print(request)
    try:
        feedback_data = request.model_dump()
        filepath = log_feedback_to_csv(feedback_data)
        print(f"[{datetime.now().isoformat()}] Feedback sur évaluation IA sauvegardé dans {filepath}")
        return {
            "message": "Feedback sur évaluation IA sauvegardé avec succès",
            "filepath": filepath,
            "feedback_id": f"{request.question_id}_fb_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR lors de la sauvegarde du feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la sauvegarde du feedback: {str(e)}"
        )
