"""
Modèles Pydantic pour la génération de questions.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class QuestionGenerationRequest(BaseModel):
    """Requête pour lancer la génération de questions."""
    num_questions_per_doc: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Nombre de questions à générer par document"
    )
    num_answers_per_question: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Nombre de réponses à générer par question"
    )
    model_name: str = Field(
        default="mistral/mistral-medium",
        description="Nom du modèle LLM à utiliser pour la génération au format <provider>/<model_name>"
    )
    document_id: Optional[int] = Field(
        default=None,
        description="ID du document spécifique à traiter. Si None, traite tous les documents validés (VALID_TEXT_RESOURCE_ID)."
    )

class QuestionGenerationResult(BaseModel):
    """Résultat de génération pour un document."""
    resource_id: int = Field(..., description="ID du document (resource_id)")
    questions_generated: int = Field(
        default=0,
        description="Nombre de questions générées pour ce document"
    )
    questions_saved: int = Field(
        default=0,
        description="Nombre de questions sauvegardées en base"
    )
    error: Optional[str] = Field(
        default=None,
        description="Message d'erreur si la génération a échoué"
    )
    status: str = Field(
        default="pending",
        description="Statut de la génération pour ce document"
    )


class QuestionGenerationJob(BaseModel):
    """Modèle pour un job de génération de questions."""
    job_id: str = Field(..., description="ID unique du job")
    job_type: str = Field(
        default="question_generation",
        description="Type de job"
    )
    status: str = Field(
        ...,
        description="Statut du job: pending, running, completed, failed, cancelled"
    )
    created_at: str = Field(..., description="Date de création (ISO format)")
    updated_at: str = Field(..., description="Date de dernière mise à jour (ISO format)")
    total_documents: int = Field(..., description="Nombre total de documents à traiter")
    processed_documents: int = Field(
        default=0,
        description="Nombre de documents déjà traités"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Paramètres du job (num_questions_per_doc, model_name)"
    )
    progress: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Progression détaillée par document (resource_id -> QuestionGenerationResult)"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Liste des erreurs rencontrées"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Message d'erreur global si le job a échoué"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "running",
                "job_type": "question_generation",
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:35:00",
                "total_documents": 2,
                "processed_documents": 1,
                "parameters": {"num_questions_per_doc": 3, "model_name": "mistral-medium"},
                "progress": {
                    "116738": {
                        "resource_id": 116738,
                        "questions_generated": 3,
                        "questions_saved": 3,
                        "error": None,
                        "status": "completed"
                    },
                    "116782": {
                        "resource_id": 116782,
                        "questions_generated": 0,
                        "questions_saved": 0,
                        "error": None,
                        "status": "pending"
                    }
                },
                "errors": [],
                "error_message": None
            }
        }


class QuestionGenerationJobListResponse(BaseModel):
    """Réponse pour la liste des jobs."""
    jobs: List[QuestionGenerationJob] = Field(
        default_factory=list,
        description="Liste de tous les jobs"
    )
    count: int = Field(
        default=0,
        description="Nombre total de jobs"
    )


class QuestionGenerationResponse(BaseModel):
    """Réponse pour la création d'un job."""
    job_id: str = Field(..., description="ID du job créé")
    message: str = Field(
        default="Job créé avec succès",
        description="Message de confirmation"
    )
    job: QuestionGenerationJob = Field(
        ...,
        description="Détails du job créé"
    )


# ============================================================================
# Modèles pour l'évaluation des messages (message_evaluator_agent)
# ============================================================================

class EvaluateMessageTypeRequest(BaseModel):
    """Requête pour évaluer une réponse avec message_evaluator_agent."""
    document_id: int = Field(..., description="ID du document")
    question_id: int = Field(..., description="ID de la question")
    question_text: str = Field(..., description="Texte de la question")
    user_answer: str = Field(..., description="Réponse de l'utilisateur à évaluer")
    manual_evaluation: Optional[bool] = Field(
        default=None,
        description="Évaluation manuelle: True=dans le contexte, False=hors sujet"
    )


class MessageEvaluatorResult(BaseModel):
    """Résultat de l'évaluation par message_evaluator_agent."""
    agent_message_type: str = Field(..., description="Type de message selon l'agent (reponse, hors_sujet, etc.)")
    agent_confidence: float = Field(..., description="Niveau de confiance de l'agent (0.0-1.0)")
    agent_explanation: str = Field(..., description="Explication de l'agent")
    manual_evaluation: Optional[bool] = Field(
        default=None,
        description="Évaluation manuelle: True=dans le contexte, False=hors sujet"
    )
    saved_to_csv: bool = Field(..., description="Indique si les résultats ont été sauvegardés dans le CSV")
    csv_file_path: Optional[str] = Field(
        default=None,
        description="Chemin vers le fichier CSV de sauvegarde"
    )
