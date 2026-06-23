"""
Router FastAPI pour la génération de questions sur les documents validés.
"""
import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from .models import (
    QuestionGenerationRequest,
    QuestionGenerationResponse,
    QuestionGenerationJob,
    QuestionGenerationJobListResponse
)
from .services import (
    create_question_generation_job,
    get_question_generation_job,
    get_all_question_generation_jobs,
    process_question_generation_job,
    get_latest_question_generation_job
)
from database.database import VALID_TEXT_RESOURCE_ID

router = APIRouter(prefix="/api/admin/questions", tags=["Admin", "Questions"])


@router.post(
    "/generate",
    response_model=QuestionGenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Lance la génération de questions",
    description="Crée un job de génération de questions pour tous les documents validés (VALID_TEXT_RESOURCE_ID). "
                "Le job est exécuté en arrière-plan et peut être suivi via les endpoints /jobs."
)
async def generate_questions(request: QuestionGenerationRequest):
    """
    Lance la génération de questions pour les documents validés.
    
    Les documents traités sont ceux définis dans VALID_TEXT_RESOURCE_ID:
    {VALID_TEXT_RESOURCE_ID}
    
    Args:
        request: QuestionGenerationRequest avec num_questions_per_doc et model_name
        
    Returns:
        QuestionGenerationResponse avec job_id et détails du job créé
    """
    # Créer le job
    job_id = create_question_generation_job(
        num_questions_per_doc=request.num_questions_per_doc,
        model_name=request.model_name
    )
    
    job = get_question_generation_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la création du job"
        )
    
    # Lancer le traitement en arrière-plan
    asyncio.create_task(process_question_generation_job(job_id))
    
    return QuestionGenerationResponse(
        job_id=job_id,
        message="Job de génération de questions créé avec succès",
        job=QuestionGenerationJob(**job)
    )


@router.get(
    "/jobs",
    response_model=QuestionGenerationJobListResponse,
    summary="Liste tous les jobs",
    description="Retourne la liste complète de tous les jobs de génération de questions."
)
async def list_question_generation_jobs():
    """
    Liste tous les jobs de génération de questions.
    
    Returns:
        QuestionGenerationJobListResponse avec la liste des jobs
    """
    jobs = get_all_question_generation_jobs()
    job_list = [QuestionGenerationJob(**job) for job in jobs.values()]
    
    return QuestionGenerationJobListResponse(
        jobs=job_list,
        count=len(job_list)
    )


@router.get(
    "/jobs/{job_id}",
    response_model=QuestionGenerationJob,
    summary="Récupère un job spécifique",
    description="Retourne les détails d'un job de génération de questions spécifique."
)
async def get_question_generation_job_by_id(job_id: str):
    """
    Récupère un job de génération de questions par son ID.
    
    Args:
        job_id: L'ID unique du job
        
    Returns:
        QuestionGenerationJob avec les détails du job
        
    Raises:
        HTTPException 404: Si le job n'existe pas
    """
    job = get_question_generation_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} introuvable"
        )
    
    return QuestionGenerationJob(**job)


@router.get(
    "/jobs/latest",
    response_model=QuestionGenerationJob,
    summary="Récupère le dernier job",
    description="Retourne le job de génération de questions le plus récent."
)
async def get_latest_question_generation_job_endpoint():
    """
    Récupère le job de génération de questions le plus récent.
    
    Returns:
        QuestionGenerationJob avec les détails du dernier job
        
    Raises:
        HTTPException 404: Si aucun job n'existe
    """
    job = get_latest_question_generation_job()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun job de génération de questions trouvé"
        )
    
    return QuestionGenerationJob(**job)


@router.get(
    "/valid-documents",
    summary="Liste les documents validés",
    description="Retourne la liste des IDs des documents validés pour la génération de questions."
)
async def get_valid_documents():
    """
    Récupère la liste des documents validés (VALID_TEXT_RESOURCE_ID).
    
    Returns:
        Liste des IDs des documents validés
    """
    return JSONResponse(
        content={
            "valid_documents": VALID_TEXT_RESOURCE_ID,
            "count": len(VALID_TEXT_RESOURCE_ID),
            "description": "IDs des documents avec extracted_text valide et vérifié"
        }
    )
