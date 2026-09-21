"""Router FastAPI pour les questions, la génération QA et l'administration.

Regroupe :
- /api/qa-single (génération de questions/réponses depuis un texte),
- /api/questions/* (consultation et mise à jour des questions d'un document),
- /api/admin/* (statistiques et documents pour l'interface d'administration).
Ces routes étaient auparavant définies dans api_server.py.
"""
import time
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

import database
from database.database import get_db_connection, get_questions_by_document_id
from question_answer.generation_services import generate_questions_single_answer_for_chunk

router = APIRouter(tags=["Questions", "Admin"])


class QASingleRequest(BaseModel):
    """Modèle de requête pour générer des questions à partir d'un texte"""
    message: Optional[str] = Field(None, description="Message ou instruction optionnel")
    document: str = Field(..., description="Texte du document/chunk sur lequel générer des questions", min_length=10)
    num_questions: int = Field(3, description="Nombre de questions à générer", ge=1, le=10)
    num_answers: Optional[int] = Field(1, description="Nombre de réponses par question à générer", ge=1, le=10)
    model: Optional[str] = Field("mistral-small", description="Modèle LLM à utiliser")


class QASinglePair(BaseModel):
    """Une paire question-réponse"""
    question: str = Field(..., description="Question générée")
    answer: str = Field(..., description="Réponse générée")


class QASingleResponse(BaseModel):
    """Réponse avec liste de questions générées"""
    QA_list: List[QASinglePair] = Field(default_factory=list, description="Liste des paires question-réponse")
    model_used: str = Field(..., description="Modèle LLM utilisé")
    generation_time: float = Field(..., description="Temps de génération en secondes")


@router.post("/api/qa-single", response_model=QASingleResponse, tags=["Query"])
async def generate_qa_single(request: QASingleRequest):
    """
    Génère des questions avec réponses à partir d'un texte donné.
    Utilise l'agent QA pour créer des questions basées sur le contenu.
    
    Args:
        request: QASingleRequest avec document, num_questions et model
        
    Returns:
        QASingleResponse avec la liste des questions générées
    """
    from agents.qa_single_agent import get_qa_agent
    import time
    
    start_time = time.time()
    
    try:
        # Extraire les informations de la requête
        document_text = request.document
        num_questions = request.num_questions
        model_name = request.model
        
        # Définir provider et model
        provider_model = model_name.split("/") if "/" in model_name else ["mistral", model_name]
        provider = provider_model[0] if len(provider_model) > 0 else "mistral"
        model = provider_model[1] if len(provider_model) > 1 else model_name
        print("generate_qa_single - model", model_name)
        qa_list, error = await generate_questions_single_answer_for_chunk(
            chunk_content=document_text,
            chunk_id="",
            document_id="",
            num_questions=num_questions,
            model_name=model_name
        )
        # Calculer le temps d'exécution
        generation_time = time.time() - start_time

        # Formater la réponse
        qa_pairs = [
            QASinglePair(question=qa.question, answer=qa.answer)
            for qa in qa_list.QA_list
        ]

        return QASingleResponse(
            QA_list=qa_pairs,
            model_used=model_name,
            generation_time=generation_time
        )
        
    except Exception as e:
        print(f"Erreur lors de la génération de questions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération de questions: {str(e)}"
        )


# Pydantic model for Question response
class QuestionResponse(BaseModel):
    question_id: int = Field(..., description="Identifiant de la question")
    content: str = Field(..., description="Contenu de la question")
    status: str = Field(..., description="Statut de la question")
    difficulty_level: int = Field(..., description="Niveau de difficulté")
    created_by: Optional[str] = Field(None, description="Créé par")
    validated_by: Optional[str] = Field(None, description="Validé par")
    chunk_id: Optional[str] = Field(None, description="ID du chunk associé")
    num_page: Optional[int] = Field(None, description="Numéro de page du chunk")
    answers: List[Dict] = Field(default_factory=list, description="Liste des réponses")

class QuestionsListResponse(BaseModel):
    document_id: str = Field(..., description="Identifiant du document")
    questions: List[QuestionResponse] = Field(..., description="Liste des questions")
    count: int = Field(..., description="Nombre total de questions")
    timestamp: str = Field(..., description="Horodatage de la réponse")


# === MODELS FOR QUESTION/ANSWER UPDATE ===
class AnswerUpdateRequest(BaseModel):
    """Modèle pour la mise à jour d'une réponse"""
    answer_id: Optional[int] = Field(None, description="ID de la réponse existante à mettre à jour")
    content: str = Field(..., description="Contenu de la réponse")
    is_correct: Optional[bool] = Field(None, description="Indique si c'est la réponse correcte")


class UpdateQuestionRequest(BaseModel):
    """Modèle pour la mise à jour d'une question et de ses réponses"""
    question_content: Optional[str] = Field(None, description="Nouveau contenu de la question")
    answers: Optional[List[AnswerUpdateRequest]] = Field(default_factory=list, description="Liste des réponses à mettre à jour ou créer")
    deleted_answer_ids: Optional[List[int]] = Field(default_factory=list, description="Liste des IDs des réponses à supprimer")


class UpdateQuestionResponse(BaseModel):
    """Modèle de réponse pour la mise à jour d'une question"""
    success: bool = Field(..., description="Indique si la mise à jour a réussi")
    message: str = Field(..., description="Message de statut")
    question: Optional[Dict] = Field(None, description="Question mise à jour avec ses réponses")


@router.get("/api/questions/{document_id}", response_model=QuestionsListResponse, tags=["Questions"])
async def get_questions_for_document(
    document_id: str,
    include_answers: bool = True,
    status_filter: Optional[str] = None,
    difficulty_filter: Optional[int] = None,
    nb_limit: Optional[int] = None
):
    """
    Récupère toutes les questions/réponses pour un document spécifique.
    
    Args:
        document_id: Identifiant du document
        include_answers: Si True, inclut les réponses associées
        status_filter: Filtre par statut (ex: "generated", "validated")
        difficulty_filter: Filtre par niveau de difficulté (1-5)
        nb_limit: Limite le nombre de questions retournées
        
    Returns:
        QuestionsListResponse: Liste des questions avec leurs réponses
    """
    try:
        async with await get_db_connection() as conn:
            questions = await get_questions_by_document_id(
                document_id, conn,
                include_answers=include_answers,
                status_filter=status_filter,
                difficulty_filter=difficulty_filter,
                nb_limit=nb_limit
            )

        # Convertir en QuestionResponse
        question_responses = []
        for q in questions:
            question_responses.append(QuestionResponse(
                question_id=q["question_id"],
                content=q["content"],
                status=q["status"],
                difficulty_level=q["difficulty_level"],
                created_by=q["created_by"],
                validated_by=q["validated_by"],
                chunk_id=q.get("chunk_id"),
                num_page=q.get("num_page"),
                answers=q.get("answers", [])
            ))
        
        return QuestionsListResponse(
            document_id=document_id,
            questions=question_responses,
            count=len(question_responses),
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR lors de la récupération des questions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des questions: {str(e)}"
        )


# === ENDPOINT UPDATE QUESTION/ANSWERS ===


@router.post("/api/questions/{question_id}/update", response_model=UpdateQuestionResponse, tags=["Questions"])
async def update_question_and_answers(
    question_id: int,
    request: UpdateQuestionRequest
):
    """
    Met à jour une question et ses réponses en base de données.
    
    Args:
        question_id: Identifiant de la question à mettre à jour
        request: UpdateQuestionRequest contenant le nouveau contenu de la question et les réponses
    
    Returns:
        UpdateQuestionResponse: Résultat de la mise à jour
    """
    try:
        async with await get_db_connection() as conn:
            # Appeler la fonction de mise à jour dans la base de données
            updated_question = await database.update_question_and_answers(
                conn=conn,
                question_id=question_id,
                question_content=request.question_content,
                answers=[
                    {
                        "answer_id": answer.answer_id,
                        "content": answer.content,
                        "is_correct": answer.is_correct if answer.is_correct is not None else False
                    }
                    for answer in request.answers
                ] if request.answers else [],
                deleted_answer_ids=request.deleted_answer_ids if request.deleted_answer_ids else []
            )
        
        if updated_question:
            return UpdateQuestionResponse(
                success=True,
                message="Question et réponses mises à jour avec succès",
                question=updated_question
            )
        else:
            return UpdateQuestionResponse(
                success=False,
                message=f"Question avec ID {question_id} non trouvée",
                question=None
            )
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR lors de la mise à jour de la question: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour de la question: {str(e)}"
        )


# MODÈLES PYDANTIC POUR L'ADMINISTRATION
# ============================================================================

class AdminStatsResponse(BaseModel):
    """Réponse pour les statistiques d'indexation"""
    documents_count: int = Field(..., description="Nombre total de documents indexés")
    chunks_count: int = Field(..., description="Nombre total de chunks indexés")
    embeddings_count: Dict[str, int] = Field(
        default_factory=dict,
        description="Nombre d'embeddings par modèle"
    )
    documents_with_extracted_text_count: int = Field(
        0,
        description="Nombre de documents avec contenu extrait (extracted_text)"
    )
    timestamp: str = Field(..., description="Horodatage de la réponse")



# ============================================================================


@router.get("/api/admin/documents", tags=["Admin"])
async def get_admin_documents():
    """
    Récupère la liste des documents existants pour l'interface d'administration.
    
    Returns:
        Liste des documents avec leurs métadonnées et indication de la présence de extracted_text.
    """
    try:
        conn = await get_db_connection()
        documents = await database.get_all_documents_with_details(conn)
        await conn.close()
        
        return {
            "documents": documents,
            "count": len(documents),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Erreur dans get_admin_documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des documents: {str(e)}"
        )


@router.get("/api/admin/stats", tags=["Admin"])
async def get_admin_stats():
    """
    Récupère les statistiques d'indexation de l'application.
    
    Note: Non implémentée pour le moment
    
    Returns:
        Erreur 501 Not Implemented
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="get_admin_stats n'est pas encore implémentée"
    )
