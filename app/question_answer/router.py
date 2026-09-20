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
from .generation_services import (
    create_question_generation_job,
    get_question_generation_job,
    get_all_question_generation_jobs,
    process_question_generation_job,
    get_latest_question_generation_job
)
from database.database import VALID_TEXT_RESOURCE_ID, get_db_connection, get_questions_by_chunk_id

router = APIRouter(prefix="/api/admin/questions", tags=["Admin", "Questions"])


@router.post(
    "/generate",
    response_model=QuestionGenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Lance la génération de questions",
    description="Crée un job de génération de questions pour un chunk spécifique, un document spécifique ou tous les documents validés (VALID_TEXT_RESOURCE_ID). "
                "Le job est exécuté en arrière-plan et peut être suivi via les endpoints /jobs."
)
async def generate_questions(request: QuestionGenerationRequest):
    """
    Lance la génération de questions pour un chunk spécifique, un document spécifique ou tous les documents validés.
    
    Priorité: chunk_id > document_id > tous les documents validés.
    Si chunk_id est fourni, seul ce chunk sera traité.
    Sinon si document_id est fourni, seul ce document sera traité.
    Sinon, tous les documents définis dans VALID_TEXT_RESOURCE_ID seront traités:
    {VALID_TEXT_RESOURCE_ID}
    
    Args:
        request: QuestionGenerationRequest avec num_questions_per_doc, model_name, document_id (optionnel) et chunk_id (optionnel)
        
    Returns:
        QuestionGenerationResponse avec job_id et détails du job créé
    """
    # Créer le job
    job_id = create_question_generation_job(
        num_questions_per_doc=request.num_questions_per_doc,
        num_answers_per_question=request.num_answers_per_question,
        model_name=request.model_name,
        document_id=request.document_id,
        chunk_id=request.chunk_id
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
    description="Retourne la liste des documents validés avec leurs document_id (text_documents.id) et titres pour la génération de questions."
)
async def get_valid_documents():
    """
    Récupère la liste des documents validés (VALID_TEXT_RESOURCE_ID) avec leurs document_id et titres.
    Les document_id correspondent aux IDs de la table text_documents (auto-incrémentés).
    
    Returns:
        Liste des documents validés avec document_id, resource_id et titre
    """
    from database.database import get_db_connection, get_resource_basic_metadata
    
    # Récupérer les document_id (text_documents.id) et titres pour chaque resource_id validé
    documents_info = []
    async with await get_db_connection() as conn:
        for resource_id in VALID_TEXT_RESOURCE_ID:
            # Récupérer le document_id (text_documents.id) pour ce resource_id
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT id FROM text_documents 
                    WHERE source_type = 'pdf' AND source_id = %s
                    LIMIT 1
                """, (str(resource_id),))
                result = await cur.fetchone()
                document_id = result[0] if result else None
            
            if document_id:
                metadata = await get_resource_basic_metadata(conn, resource_id)
                title = metadata.get("title", f"Document {resource_id}")
                documents_info.append({
                    "document_id": document_id,
                    "resource_id": resource_id,
                    "title": title
                })
    
    return JSONResponse(
        content={
            "valid_documents": VALID_TEXT_RESOURCE_ID,
            "documents": documents_info,
            "count": len(documents_info),
            "description": "Documents avec extracted_text valide et vérifié"
        }
    )

@router.get(
    "/chunk/{chunk_id}",
    summary="Questions et réponses associées à un chunk",
    description="Retourne les questions (avec leurs réponses) associées à un chunk précis "
                "(text_chunks.id) via la table question_chunks.",
)
async def get_chunk_questions(chunk_id: str):
    """Récupère les questions et réponses associées à un chunk."""
    try:
        async with await get_db_connection() as conn:
            questions = await get_questions_by_chunk_id(chunk_id, conn, include_answers=True)
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des questions: {str(e)}",
        )

    return JSONResponse(content={
        "chunk_id": chunk_id,
        "questions": questions,
        "count": len(questions),
    })

@router.post(
    "/save",
    summary="Sauvegarde une question manuellement",
    description="Sauvegarde une question avec ses réponses dans la base de données. "
                "Utilisé pour valider les questions générées localement dans le navigateur."
)
async def save_question_manually(request: dict):
    """
    Sauvegarde une question avec ses réponses dans la base de données.
    
    Args:
        request: Dictionnaire avec question, answers (liste), chunk_id, model, difficulty_level
        
    Returns:
        JSONResponse avec succès/error et l'ID de la question sauvegardée
    """
    from database.database import save_question_to_db, get_db_connection
    
    try:
        required_fields = ['question']
        optional_fields = ['answers', 'chunk_id', 'model', 'difficulty_level']
        
        for field in required_fields:
            if field not in request:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Champ manquant: {field}"
                )
        
        # Valeurs par défaut
        answers = request.get('answers', [])
        chunk_id = request.get('chunk_id')
        model = request.get('model', 'local-generation')
        difficulty_level = request.get('difficulty_level', 3)
        
        # Convertir chunk_id en string si c'est un nombre
        if chunk_id:
            chunk_id = str(chunk_id)
        
        # Sauvegarder dans la base de données
        async with await get_db_connection() as conn :
            question_id = await save_question_to_db(
                question=request['question'],
                answers=answers,
                chunk_id=chunk_id,
                conn=conn,
                model=model,
                difficulty_level=difficulty_level
            )
        
        return JSONResponse(
            content={
                "success": True,
                "question_id": question_id,
                "message": "Question sauvegardée avec succès"
            }
        )
        
    except Exception as e:
        print(f"Erreur lors de la sauvegarde de la question: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la sauvegarde de la question: {str(e)}"
        )


# ============================================================================
# NOUVEAUX ENDPOINTS POUR LA GÉNÉRATION DE RÉPONSES
# ============================================================================

from pydantic import BaseModel, Field
from typing import List, Optional


class GenerateAnswersRequest(BaseModel):
    """Requête pour générer des réponses à une question"""
    question_text: str = Field(..., description="Texte de la question")
    document_context: str = Field(..., description="Contexte du document")
    num_answers: int = Field(default=1, ge=1, le=10, description="Nombre de réponses à générer")
    model_name: str = Field(default="mistral-small", description="Modèle LLM à utiliser")


class GenerateAnswersResponse(BaseModel):
    """Réponse avec les réponses générées"""
    question: str
    answers: List[str]
    model_used: str


@router.post(
    "/generate-answers",
    response_model=GenerateAnswersResponse,
    summary="Génère des réponses à une question",
    description="Génère plusieurs réponses pour une question donnée, en utilisant le contexte du document."
)
async def generate_answers(request: GenerateAnswersRequest):
    """
    Génère des réponses multiples pour une question.
    Utilise l'agent qa_agent pour générer les réponses.
    """
    from agents import qa_agent
    
    # Définir provider et model
    provider, model = tuple(request.model_name.split("/")) if "/" in request.model_name else ("mistral", request.model_name)
    
    agent = qa_agent.get_qa_agent(model=model, provider=provider, async_mode=True)
    
    input_schema = qa_agent.QuestionRequestInput(
        message=(
            f"Question: {request.question_text}\n\n"
            f"Génère exactement {request.num_answers} réponses différentes à la question ci-dessus, "
            f"en t'appuyant uniquement sur le contexte fourni. Ne génère aucune question."
        ),
        document=request.document_context,
        num_questions=1,
        num_answers_per_question=request.num_answers
    )
    
    response = await agent.run_async(input_schema)
    
    # Récupérer les réponses de la première question (unique) générée
    answers = response.questions_answers[0].answers_text[:request.num_answers] if response.questions_answers else []
    
    return GenerateAnswersResponse(
        question=request.question_text,
        answers=answers,
        model_used=request.model_name
    )


class AddAnswerRequest(BaseModel):
    """Requête pour ajouter une réponse à une question existante"""
    answer_text: str = Field(..., description="Texte de la réponse à ajouter")
    is_correct: bool = Field(default=True, description="Si la réponse est correcte")
    model_name: str = Field(default="", description="Modèle utilisé pour générer cette réponse")


class AddAnswerResponse(BaseModel):
    """Réponse après ajout d'une réponse"""
    success: bool
    answer_id: Optional[int] = None
    message: str


@router.post(
    "/{question_id}/add-answer",
    response_model=AddAnswerResponse,
    summary="Ajoute une réponse à une question existante",
    description="Ajoute une nouvelle réponse à une question existante dans la base de données."
)
async def add_answer_to_question(question_id: int, request: AddAnswerRequest):
    """
    Ajoute une réponse à une question existante.
    """
    try:
        async with await get_db_connection() as conn:
            async with conn.cursor() as cur:
                # Vérifier que la question existe
                await cur.execute("""
                    SELECT question_id FROM text_questions WHERE question_id = %s
                """, (question_id,))
                result = await cur.fetchone()
                
                if not result:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Question {question_id} introuvable"
                    )
                
                # Insérer la nouvelle réponse
                await cur.execute("""
                    INSERT INTO text_question_answers (question_id, content, is_correct, created_by)
                    VALUES (%s, %s, %s, %s)
                """, (question_id, request.answer_text, request.is_correct, None))
                
                answer_id = cur.lastrowid
                await conn.commit()
                
                return AddAnswerResponse(
                    success=True,
                    answer_id=answer_id,
                    message=f"Réponse ajoutée avec succès (ID: {answer_id})"
                )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'ajout de la réponse: {str(e)}"
        )
