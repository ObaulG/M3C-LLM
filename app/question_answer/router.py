"""
Router FastAPI pour la génération de questions sur les documents validés.
"""
import asyncio
from typing import Optional, List

import database
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException, status, Cookie, Depends
from fastapi.responses import JSONResponse

from .models import (
    QuestionGenerationRequest,
    QuestionGenerationResponse,
    QuestionGenerationJob,
    QuestionGenerationJobListResponse,
    CompareGenerationRequest,
    FactGenerationRequest,
    FactGenerationResponse,
)
from .fact_generation_services import (
    create_fact_generation_job,
    get_fact_generation_job,
    get_all_fact_generation_jobs,
    process_fact_generation_job,
)
from .generation_services import (
    create_question_generation_job,
    get_question_generation_job,
    get_all_question_generation_jobs,
    process_question_generation_job,
    get_latest_question_generation_job
)
from .compare_generation_services import (
    create_compare_generation_job,
    get_compare_generation_job,
    process_compare_generation_job,
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
    if request.start_page is not None and request.end_page is not None \
            and request.end_page < request.start_page:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_page doit être supérieur ou égal à start_page."
        )

    job_id = create_question_generation_job(
        num_questions_per_doc=request.num_questions_per_doc,
        num_answers_per_question=request.num_answers_per_question,
        model_name=request.model_name,
        document_id=request.document_id,
        chunk_id=request.chunk_id,
        user_prompt=request.user_prompt,
        start_page=request.start_page,
        end_page=request.end_page,
        use_batch=request.use_batch,
        generate_facts=request.generate_facts
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


@router.post(
    "/facts/generate",
    response_model=FactGenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Lance la génération des faits des réponses d'un document",
    description="Crée un job qui extrait les affirmations (faits) de toutes les réponses de référence "
                "d'un document (ou de tous les documents) qui n'en ont pas encore dans text_answer_facts. "
                "Le job est exécuté en arrière-plan et peut être suivi via /facts/jobs."
)
async def generate_answer_facts(request: FactGenerationRequest):
    """
    Lance la génération des faits pour toutes les réponses de référence sans faits.

    Args:
        request: FactGenerationRequest avec document_id (optionnel), model_name,
                 use_batch (optionnel) et la plage de pages (optionnelle)

    Returns:
        FactGenerationResponse avec job_id et détails du job créé
    """
    if request.start_page is not None and request.end_page is not None \
            and request.end_page < request.start_page:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_page doit être supérieur ou égal à start_page."
        )

    job_id = create_fact_generation_job(
        document_id=request.document_id,
        model_name=request.model_name,
        use_batch=request.use_batch,
        start_page=request.start_page,
        end_page=request.end_page
    )

    job = get_fact_generation_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la création du job"
        )

    asyncio.create_task(process_fact_generation_job(job_id))

    return FactGenerationResponse(
        job_id=job_id,
        message="Job de génération des faits créé avec succès",
        job=QuestionGenerationJob(**job)
    )


@router.get(
    "/facts/jobs",
    response_model=QuestionGenerationJobListResponse,
    summary="Liste les jobs de génération des faits",
    description="Retourne la liste de tous les jobs d'extraction des faits (type facts-generation)."
)
async def list_fact_generation_jobs():
    jobs = get_all_fact_generation_jobs()
    job_list = [QuestionGenerationJob(**job) for job in jobs.values()]
    return QuestionGenerationJobListResponse(jobs=job_list, count=len(job_list))


@router.get(
    "/facts/jobs/{job_id}",
    response_model=QuestionGenerationJob,
    summary="Récupère un job de génération des faits",
    description="Retourne un job d'extraction des faits par son ID, avec sa progression, "
                "ses erreurs et la consommation (tokens et coût) de ses appels LLM."
)
async def get_fact_generation_job_endpoint(job_id: str):
    job = get_fact_generation_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} introuvable"
        )
    return QuestionGenerationJob(**job)


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
    question_text: Optional[str] = Field(default=None, description="Texte de la question ( requis si question_id absent)")
    document_context: Optional[str] = Field(default=None, description="Contexte du document (requis si question_id absent)")
    question_id: Optional[int] = Field(default=None, description="ID de la question existante : la question et son contexte (chunks) sont récupérés en base")
    num_answers: int = Field(default=1, ge=1, le=10, description="Nombre de réponses à générer")
    model_name: str = Field(default="mistral-small-2603", description="Modèle LLM à utiliser")
    user_prompt: Optional[str] = Field(
        default=None,
        description="Instructions personnalisées de l'utilisateur pour adapter la génération des réponses au contenu du document"
    )


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
    Si question_id est fourni, la question et son contexte (chunks associés)
    sont récupérés depuis la base de données.
    """
    from agents import qa_agent

    question_text = request.question_text
    document_context = request.document_context

    if request.question_id is not None:
        if question_text or document_context:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fournissez soit question_id, soit question_text + document_context, mais pas les deux."
            )
        async with await get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT content FROM text_questions WHERE question_id = %s
                """, (request.question_id,))
                row = await cur.fetchone()
                if not row:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Question {request.question_id} introuvable"
                    )
                question_text = row[0]

                await cur.execute("""
                    SELECT c.content
                    FROM text_question_chunks qc
                    JOIN text_chunks c ON c.id = qc.chunk_id
                    WHERE qc.question_id = %s
                    ORDER BY c.num_page, c.position_in_page
                """, (request.question_id,))
                chunk_rows = await cur.fetchall()

        document_context = "\n\n".join(row[0] for row in chunk_rows) if chunk_rows else ""

    if not question_text or not document_context:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="question_id (existant en base) ou question_text + document_context sont requis."
        )

    # Définir provider et model
    provider, model = tuple(request.model_name.split("/")) if "/" in request.model_name else ("mistral", request.model_name)

    agent = qa_agent.get_qa_agent(model=model, provider=provider, async_mode=True)

    user_prompt_instructions = (
        f"\n\nInstructions supplémentaires de l'utilisateur :\n{request.user_prompt.strip()}"
        if (request.user_prompt and request.user_prompt.strip()) else ""
    )

    input_schema = qa_agent.QuestionRequestInput(
        message=(
            f"Question: {question_text}\n\n"
            f"Génère exactement {request.num_answers} réponses différentes à la question ci-dessus, "
            f"en t'appuyant uniquement sur le contexte fourni. Ne génère aucune question."
            f"{user_prompt_instructions}"
        ),
        document=document_context,
        num_questions=1,
        num_answers_per_question=request.num_answers
    )

    response = await agent.run_async(input_schema)

    # Récupérer les réponses de la première question (unique) générée
    answers = response.questions_answers[0].answers_text[:request.num_answers] if response.questions_answers else []

    return GenerateAnswersResponse(
        question=question_text,
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


class DeleteAllAnswersResponse(BaseModel):
    """Réponse après la suppression de toutes les réponses d'une question"""
    success: bool
    question_id: int
    deleted_answers: int
    deleted_facts: int
    message: str


@router.post(
    "/{question_id}/delete-answers",
    response_model=DeleteAllAnswersResponse,
    summary="Supprime toutes les réponses d'une question",
    description="Supprime toutes les réponses d'une question existante, ainsi que les faits (affirmations) associés à chaque réponse."
)
async def delete_all_answers(question_id: int):
    """
    Supprime toutes les réponses d'une question et leurs faits associés.
    """
    from database.database import delete_answer_facts

    try:
        async with await get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT answer_id FROM text_question_answers WHERE question_id = %s
                """, (question_id,))
                answer_rows = await cur.fetchall()

                if not answer_rows:
                    return DeleteAllAnswersResponse(
                        success=True,
                        question_id=question_id,
                        deleted_answers=0,
                        deleted_facts=0,
                        message=f"Aucune réponse à supprimer pour la question {question_id}"
                    )

                deleted_facts = 0
                for row in answer_rows:
                    deleted_facts += await delete_answer_facts(row[0], conn)

                await cur.execute("""
                    DELETE FROM text_question_answers WHERE question_id = %s
                """, (question_id,))
                deleted_answers = cur.rowcount
                await conn.commit()

                return DeleteAllAnswersResponse(
                    success=True,
                    question_id=question_id,
                    deleted_answers=deleted_answers,
                    deleted_facts=deleted_facts,
                    message=f"{deleted_answers} réponse(s) et {deleted_facts} fait(s) supprimés pour la question {question_id}"
                )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression des réponses: {str(e)}"
        )


class GenerateAnswerFactsResponse(BaseModel):
    """Réponse après la génération des faits d'une réponse"""
    success: bool
    answer_id: int
    facts: List[dict] = []
    message: str


class UpdateFactContentRequest(BaseModel):
    """Requête pour mettre à jour le contenu d'un fait de réponse"""
    content: str = Field(..., min_length=1, description="Nouveau contenu du fait")


class UpdateFactContentResponse(BaseModel):
    """Réponse après la mise à jour du contenu d'un fait"""
    success: bool
    fact_id: int
    content: str
    message: str


class DeleteFactResponse(BaseModel):
    """Réponse après la suppression d'un fait"""
    success: bool
    fact_id: int
    message: str


class AddAnswerFactRequest(BaseModel):
    """Requête pour ajouter manuellement un fait à une réponse"""
    content: str = Field(..., min_length=1, description="Contenu du fait")
    importance: str = Field("essential", description="Importance du fait: essential ou optional")


class AddAnswerFactResponse(BaseModel):
    """Réponse après l'ajout manuel d'un fait"""
    success: bool
    answer_id: int
    fact_id: int
    content: str
    importance: str
    message: str


class UpdateFactImportanceRequest(BaseModel):
    """Requête pour basculer l'importance d'un fait de réponse"""
    importance: str = Field(..., description="Nouvelle importance : " + "essential" + " ou " + "optional")


class UpdateFactImportanceResponse(BaseModel):
    """Réponse après la mise à jour de l'importance d'un fait"""
    success: bool
    fact_id: int
    importance: str
    message: str


@router.post(
    "/facts/{fact_id}/update-importance",
    response_model=UpdateFactImportanceResponse,
    summary="Bascule l'importance d'un fait de réponse",
    description="Met à jour l'importance (" + "essential" + "/" + "optional" + ") d'une affirmation "
                "dans text_answer_facts et retourne la nouvelle valeur."
)
async def update_fact_importance(fact_id: int, request: UpdateFactImportanceRequest):
    """
    Met à jour l'importance d'un fait de réponse en base.
    """
    from database.database import update_answer_fact_importance

    if request.importance not in ("essential", "optional"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'importance doit être " + "'essential'" + " ou " + "'optional'"
        )

    try:
        async with await get_db_connection() as conn:
            updated = await update_answer_fact_importance(fact_id, request.importance, conn)

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fait {fact_id} introuvable"
            )

        return UpdateFactImportanceResponse(
            success=True,
            fact_id=fact_id,
            importance=request.importance,
            message="Importance mise à jour avec succès"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour de l'importance: {str(e)}"
        )


@router.post(
    "/facts/{fact_id}/update-content",
    response_model=UpdateFactContentResponse,
    summary="Met à jour le contenu d'un fait de réponse",
    description="Modifie le contenu d'une affirmation dans text_answer_facts."
)
async def update_fact_content(fact_id: int, request: UpdateFactContentRequest):
    """
    Met à jour le contenu d'un fait de réponse en base.
    """
    from database.database import update_answer_fact_content

    try:
        async with await get_db_connection() as conn:
            updated = await update_answer_fact_content(fact_id, request.content.strip(), conn)

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fait {fact_id} introuvable"
            )

        return UpdateFactContentResponse(
            success=True,
            fact_id=fact_id,
            content=request.content.strip(),
            message="Contenu mis à jour avec succès"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour du contenu: {str(e)}"
        )


@router.post(
    "/facts/{fact_id}/delete",
    response_model=DeleteFactResponse,
    summary="Supprime un fait de réponse",
    description="Supprime une affirmation de text_answer_facts."
)
async def delete_fact(fact_id: int):
    """
    Supprime un fait de réponse en base.
    """
    from database.database import delete_answer_fact

    try:
        async with await get_db_connection() as conn:
            deleted = await delete_answer_fact(fact_id, conn)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fait {fact_id} introuvable"
            )

        return DeleteFactResponse(
            success=True,
            fact_id=fact_id,
            message="Fait supprimé avec succès"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression du fait: {str(e)}"
        )


@router.post(
    "/answers/{answer_id}/add-fact",
    response_model=AddAnswerFactResponse,
    summary="Ajoute manuellement un fait à une réponse",
    description="Insère une nouvelle affirmation dans text_answer_facts pour la réponse donnée."
)
async def add_answer_fact(answer_id: int, request: AddAnswerFactRequest):
    """
    Ajoute manuellement un fait à une réponse en base.
    """
    from database.database import insert_answer_facts

    importance = request.importance if request.importance in ("essential", "optional") else "essential"

    try:
        async with await get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT answer_id FROM text_question_answers WHERE answer_id = %s
                """, (answer_id,))
                row = await cur.fetchone()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Réponse {answer_id} introuvable"
                )

            fact_ids = await insert_answer_facts(
                answer_id,
                [{"content": request.content.strip(), "importance": importance}],
                conn,
                model="manual",
            )

        return AddAnswerFactResponse(
            success=True,
            answer_id=answer_id,
            fact_id=fact_ids[0],
            content=request.content.strip(),
            importance=importance,
            message="Fait ajouté avec succès"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'ajout du fait: {str(e)}"
        )


@router.post(
    "/answers/{answer_id}/generate-facts",
    response_model=GenerateAnswerFactsResponse,
    summary="Génère les faits (affirmations) d'une réponse de référence",
    description="Extrait les affirmations constituant une réponse de référence via l'agent fact_extractor, "
                "remplace les faits existants dans text_answer_facts et retourne les faits générés."
)
async def generate_answer_facts(answer_id: int, model_name: str = "mistral-small-2603"):
    """
    Génère les faits d'une réponse de référence et les sauvegarde en base.
    """
    from agents.fact_extractor import get_answer_facts_agent, FactExtractionInput
    from database.database import insert_answer_facts, delete_answer_facts

    try:
        async with await get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT content FROM text_question_answers WHERE answer_id = %s
                """, (answer_id,))
                row = await cur.fetchone()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Réponse {answer_id} introuvable"
                )
            provider, model = tuple(model_name.split("/"))
            print(provider, model)
            agent = get_answer_facts_agent(provider=provider, model=model)
            output = agent.run(FactExtractionInput(paragraph=row[0]))
            facts = [
                {
                    "content": f.content,
                    "importance": f.importance if f.importance in ("essential", "optional") else "essential",
                }
                for f in output.facts
            ]

            if not facts:
                return GenerateAnswerFactsResponse(
                    success=False,
                    answer_id=answer_id,
                    facts=[],
                    message="Aucun fait n'a pu être extrait de cette réponse"
                )

            await delete_answer_facts(answer_id, conn)
            fact_ids = await insert_answer_facts(answer_id, facts, conn, model=model_name)
            for fact, fact_id in zip(facts, fact_ids):
                fact["fact_id"] = fact_id

            return GenerateAnswerFactsResponse(
                success=True,
                answer_id=answer_id,
                facts=facts,
                message=f"{len(facts)} fait(s) généré(s) avec succès"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération des faits: {str(e)}"
        )


# ============================================================================
# GÉNÉRATION COMPARATIVE MULTI-MODÈLES
# ============================================================================

async def require_authenticated_user(
    m3c_api_key: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = None,
):
    """Dépendance FastAPI : exige un utilisateur authentifié, sans contrainte de rôle."""
    import auth

    user_id = auth.user_id_from_token(m3c_api_key)
    if user_id is None:
        user_id = auth.user_id_from_authorization(authorization)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise.",
        )
    user = await auth.get_user_by_id(user_id)
    return user


@router.get(
    "/compare-generation/chunks/{document_id}",
    summary="Chunks d'un document pour la comparaison multi-modèles",
    description="Retourne les chunks d'un document (text_chunks) avec un aperçu de leur contenu, "
                "pour la sélection multi-chunks/multi-documents de la génération comparative.",
)
async def get_compare_chunks(document_id: int, user: dict = Depends(require_authenticated_user)):
    """Liste les chunks d'un document pour la sélection dans la comparaison multi-modèles."""
    try:
        async with await get_db_connection() as conn:
            chunks = await database.get_all_text_chunks(conn, document_id)
    except Exception as e:
        print(f"Erreur dans get_compare_chunks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des chunks: {str(e)}",
        )

    return JSONResponse(content={
        "document_id": document_id,
        "chunks": [
            {
                "chunk_id": c["id"],
                "document_id": c.get("document_id"),
                "num_page": c.get("num_page"),
                "position_in_page": c.get("position_in_page"),
                "character_count": c.get("character_count"),
                "token_count": c.get("token_count"),
                "preview": (c.get("content") or "")[:200],
            }
            for c in chunks
        ],
        "count": len(chunks),
    })


@router.post(
    "/compare-generation",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Lance la génération comparative multi-modèles",
    description="Pour chaque chunk sélectionné et chaque modèle (au moins 3), génère les questions/réponses, "
                "puis les faits de chaque réponse, ainsi que les éléments de connaissance. "
                "Aucune donnée n'est sauvegardée en base : les résultats restent en mémoire et sont "
                "consultables via /compare-generation/jobs/{job_id}.",
)
async def compare_generation(
    request: CompareGenerationRequest,
    user: dict = Depends(require_authenticated_user),
):
    """
    Lance un job de génération comparative : questions/réponses puis faits,
    plus éléments de connaissance, pour chaque chunk et chaque modèle.
    """
    if len(set(request.models)) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sélectionnez au moins 3 modèles distincts à comparer.",
        )

    job_id = create_compare_generation_job(
        chunk_ids=request.chunk_ids,
        models=request.models,
        num_questions=request.num_questions_per_chunk,
        user_prompt=request.user_prompt,
    )
    job = get_compare_generation_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la création du job de comparaison",
        )

    asyncio.create_task(process_compare_generation_job(job_id))

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "job_id": job_id,
            "message": "Job de génération comparative créé avec succès",
            "status": job.get("status"),
        },
    )


@router.get(
    "/compare-generation/jobs/{job_id}",
    summary="Résultats d'un job de génération comparative",
    description="Retourne l'état et les résultats (en mémoire, non persistés en base) d'un job "
                "de génération comparative.",
)
async def get_compare_generation_job_endpoint(job_id: str, user: dict = Depends(require_authenticated_user)):
    """Récupère un job de génération comparative avec ses résultats."""
    job = get_compare_generation_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job de comparaison {job_id} introuvable",
        )
    return JSONResponse(content=job)
