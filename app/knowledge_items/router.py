"""Router FastAPI pour la génération de knowledge_items à partir de chunks de documents.

Ce router permet de :
- lister les documents validés (VALID_TEXT_RESOURCE_ID) et leurs chunks,
- générer des knowledge_items à partir d'un chunk précis via un appel LLM
  (agents.knowledge_item_agent.generate_knowledge_items_from_chunk),
- sauvegarder les knowledge_items générés dans le schéma user_knowledge_model.sql
  (knowledge_items, knowledge_item_entities, knowledge_item_themes, knowledge_sources,
  et les tables de référence entities / themes / knowledge_resources).

La persistance s'appuie sur la fonction existante
save_knowledge_candidates_to_db du module agents.knowledge_element_extractor.
"""
import time
from typing import Optional, List

import aiomysql
from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import JSONResponse
from pydantic import Field

from database.database import (
    get_db_connection,
    get_chunk_by_id,
    get_valid_documents_with_metadata,
    get_or_create_knowledge_resource,
    get_knowledge_items,
    get_questions_by_chunk_id,
    DB_CONFIG,
    VALID_TEXT_RESOURCE_ID,
)


async def _get_dict_cursor_connection():
    """Ouvre une connexion MySQL avec DictCursor.

    Requis par save_knowledge_candidates_to_db (agents.knowledge_element_extractor)
    qui accède aux résultats par nom de colonne (result['id']). get_db_connection()
    retourne un curseur tuple.
    """
    return await aiomysql.connect(**DB_CONFIG, cursorclass=aiomysql.DictCursor)
from agents.knowledge_element_extractor import (
    save_knowledge_candidates_to_db,
    KnowledgeItemCandidate,
    EntityCandidate,
    ThemeCandidate,
    SourceReference,
    EntityType,
)
from agents.knowledge_item_agent import (
    generate_knowledge_items_from_chunk,
    generate_knowledge_items_from_questions,
    KnowledgeItemSchema,
    QAItemSchema,
)

from .models import (
    KnowledgeGenerationRequest,
    KnowledgeGenerationFromQuestionsRequest,
    KnowledgeGenerationResponse,
    KnowledgeSaveRequest,
    KnowledgeSaveResponse,
    KnowledgeSaveResult,
    KnowledgeItemModel,
    EntityCandidateModel,
    ThemeCandidateModel,
    SourceReferenceModel,
    QAItemRequestModel,
)


router = APIRouter(prefix="/api/admin/knowledge-items", tags=["Admin", "Knowledge Items"])


# ----------------------------------------------------------------------------
# Conversion entre modèles Pydantic et dataclasses de l'extracteur
# ----------------------------------------------------------------------------

def _schema_to_model(item: KnowledgeItemSchema) -> KnowledgeItemModel:
    """Convertit un KnowledgeItemSchema (sortie de l'agent) en modèle Pydantic
    de réponse API (KnowledgeItemModel). Les deux structures sont isomorphes."""
    return KnowledgeItemModel(
        proposition=item.proposition,
        summary=item.summary,
        entities=[
            EntityCandidateModel(name=e.name, type=e.type, confidence=e.confidence)
            for e in item.entities
        ],
        themes=[
            ThemeCandidateModel(name=t.name, confidence=t.confidence)
            for t in item.themes
        ],
        source_reference=SourceReferenceModel(
            document_id=item.source_reference.document_id,
            chunk_id=item.source_reference.chunk_id,
            excerpt=item.source_reference.excerpt or "",
            page=item.source_reference.page,
            position_in_page=item.source_reference.position_in_page,
            position_start=item.source_reference.position_start,
            position_end=item.source_reference.position_end,
            uri=item.source_reference.uri,
        ),
        confidence=item.confidence,
        is_verified=item.is_verified,
        verification_notes=item.verification_notes,
    )


def _model_to_candidate(item: KnowledgeItemModel) -> KnowledgeItemCandidate:
    """Convertit un KnowledgeItemModel (API) en KnowledgeItemCandidate (dataclass)
    attendu par save_knowledge_candidates_to_db pour la persistance."""
    valid_entity_types = {t.value for t in EntityType}
    entities = [
        EntityCandidate(
            name=e.name,
            type=EntityType(e.type) if e.type in valid_entity_types else EntityType.OTHER,
            confidence=e.confidence,
        )
        for e in item.entities
    ]
    themes = [ThemeCandidate(name=t.name, confidence=t.confidence) for t in item.themes]
    source_ref = SourceReference(
        document_id=item.source_reference.document_id,
        chunk_id=item.source_reference.chunk_id,
        excerpt=item.source_reference.excerpt,
        page=item.source_reference.page,
        position_in_page=item.source_reference.position_in_page,
        position_start=item.source_reference.position_start,
        position_end=item.source_reference.position_end,
        uri=item.source_reference.uri,
    )
    return KnowledgeItemCandidate(
        proposition=item.proposition,
        summary=item.summary,
        entities=entities,
        themes=themes,
        source_reference=source_ref,
        confidence=item.confidence,
        is_verified=item.is_verified,
        verification_notes=item.verification_notes,
    )


# ----------------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------------

@router.get(
    "/valid-documents",
    summary="Liste les documents validés",
    description="Retourne la liste des documents validés (VALID_TEXT_RESOURCE_ID) avec "
                "leurs document_id (text_documents.id), resource_id et titres, "
                "pour la sélection d'un document source de knowledge_items.",
)
async def get_valid_documents():
    """Récupère la liste des documents validés (VALID_TEXT_RESOURCE_ID)."""
    async with await get_db_connection() as conn:
        documents_info = await get_valid_documents_with_metadata(conn)

    return JSONResponse(content={
        "valid_documents": VALID_TEXT_RESOURCE_ID,
        "documents": documents_info,
        "count": len(documents_info),
        "description": "Documents avec extracted_text valide et vérifié",
    })


@router.get(
    "/chunks/{chunk_id}",
    summary="Récupère un chunk précis",
    description="Retourne le contenu et les métadonnées d'un chunk précis (text_chunks.id).",
)
async def get_chunk(chunk_id: int):
    """Récupère un chunk spécifique par son ID."""
    try:
        async with await get_db_connection() as conn:
            chunk = await get_chunk_by_id(conn, chunk_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération du chunk: {str(e)}",
        )

    if not chunk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chunk {chunk_id} introuvable",
        )

    return JSONResponse(content={"chunk": chunk})


@router.get(
    "/chunks/{chunk_id}/questions",
    summary="Questions et réponses associées à un chunk",
    description="Retourne les questions (avec leurs réponses) associées à un chunk précis "
                "(text_chunks.id) via la table question_chunks. Réutilise get_questions_by_chunk_id.",
)
async def get_chunk_questions(chunk_id: int):
    """Récupère les questions et réponses associées à un chunk."""
    try:
        async with await get_db_connection() as conn:
            questions = await get_questions_by_chunk_id(str(chunk_id), conn, include_answers=True)
    except Exception as e:
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
    "/generate",
    response_model=KnowledgeGenerationResponse,
    summary="Génère des knowledge_items pour un chunk",
    description="Extrait des knowledge_items (propositions vérifiables + entités + thèmes + "
                "source) à partir du contenu d'un chunk précis via un appel LLM "
                "(agents.knowledge_item_agent.generate_knowledge_items_from_chunk).",
)
async def generate_knowledge_items(request: KnowledgeGenerationRequest):
    """Génère des knowledge_items à partir d'un chunk précis via un LLM."""
    start_time = time.time()

    # 1. Récupérer le chunk
    try:
        async with await get_db_connection() as conn:
            chunk = await get_chunk_by_id(conn, request.chunk_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération du chunk: {str(e)}",
        )

    if not chunk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chunk {request.chunk_id} introuvable",
        )

    text = chunk.get("content", "")
    if not text or not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le chunk {request.chunk_id} ne contient pas de texte exploitable",
        )

    # 2. Extraction via LLM (AtomicAgent knowledge_item_agent)
    document_id_str = str(request.document_id) if request.document_id else str(chunk.get("document_id", ""))

    try:
        schemas = await generate_knowledge_items_from_chunk(
            text=text,
            chunk_id=str(request.chunk_id),
            document_id=document_id_str,
            page=chunk.get("num_page"),
            position_in_page=chunk.get("position_in_page"),
            model=request.model,
        )
    except Exception as e:
        print(f"Erreur lors de l'extraction de knowledge_items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'extraction: {str(e)}",
        )

    # 3. Conversion en modèles Pydantic de réponse
    knowledge_items = [_schema_to_model(s) for s in schemas]

    generation_time = time.time() - start_time

    return KnowledgeGenerationResponse(
        chunk_id=request.chunk_id,
        document_id=request.document_id if request.document_id is not None else chunk.get("document_id"),
        model=request.model,
        knowledge_items=knowledge_items,
        count=len(knowledge_items),
        generation_time=round(generation_time, 3),
    )


@router.post(
    "/generate-from-questions",
    response_model=KnowledgeGenerationResponse,
    summary="Génère des knowledge_items à partir des questions/réponses d'un chunk",
    description="Extrait des knowledge_items (propositions vérifiables + entités + thèmes + "
                "source) à partir des questions/réponses associées à un chunk via un appel "
                "LLM (agents.knowledge_item_agent.generate_knowledge_items_from_questions). "
                "Permet de comparer cette extraction à celle réalisée directement depuis le "
                "chunk (endpoint /generate).",
)
async def generate_knowledge_items_from_questions_endpoint(request: KnowledgeGenerationFromQuestionsRequest):
    """Génère des knowledge_items à partir des questions/réponses d'un chunk via un LLM."""
    start_time = time.time()

    if not request.qa_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune paire question/réponses fournie",
        )

    # Récupérer les métadonnées du chunk (page, position) si un chunk_id est fourni
    page = None
    position_in_page = None
    chunk_document_id = request.document_id
    if request.chunk_id:
        try:
            async with await get_db_connection() as conn:
                chunk = await get_chunk_by_id(conn, request.chunk_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur lors de la récupération du chunk: {str(e)}",
            )
        if chunk:
            page = chunk.get("num_page")
            position_in_page = chunk.get("position_in_page")
            if chunk_document_id is None:
                chunk_document_id = chunk.get("document_id")

    document_id_str = str(chunk_document_id) if chunk_document_id is not None else None

    # Convertir les modèles Pydantic en QAItemSchema attendus par l'agent
    qa_items = [
        QAItemSchema(
            question_id=qa.question_id,
            question=qa.question,
            answers=list(qa.answers),
        )
        for qa in request.qa_items
    ]

    try:
        schemas = await generate_knowledge_items_from_questions(
            qa_items=qa_items,
            chunk_id=str(request.chunk_id) if request.chunk_id is not None else None,
            document_id=document_id_str,
            page=page,
            position_in_page=position_in_page,
            model=request.model,
        )
    except Exception as e:
        print(f"Erreur lors de l'extraction de knowledge_items depuis les questions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'extraction: {str(e)}",
        )

    knowledge_items = [_schema_to_model(s) for s in schemas]

    generation_time = time.time() - start_time

    return KnowledgeGenerationResponse(
        chunk_id=request.chunk_id,
        document_id=chunk_document_id,
        model=request.model,
        knowledge_items=knowledge_items,
        count=len(knowledge_items),
        generation_time=round(generation_time, 3),
    )


@router.post(
    "/save",
    response_model=KnowledgeSaveResponse,
    summary="Sauvegarde des knowledge_items en base",
    description="Sauvegarde les knowledge_items fournis dans le schéma user_knowledge_model.sql : "
                "création/récupération des entités, thèmes et ressource, insertion dans "
                "knowledge_items, knowledge_item_entities, knowledge_item_themes et knowledge_sources.",
)
async def save_knowledge_items(request: KnowledgeSaveRequest):
    """Sauvegarde les knowledge_items générés dans la base MySQL."""
    if not request.knowledge_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun knowledge_item à sauvegarder",
        )

    # Construire le titre de la ressource si non fourni
    resource_title = request.resource_title
    if not resource_title:
        if request.document_id is not None:
            resource_title = f"Document {request.document_id}"
        elif request.chunk_id is not None:
            resource_title = f"Chunk {request.chunk_id}"
        else:
            resource_title = "Document inconnu"

    # Convertir les modèles Pydantic en KnowledgeItemCandidate
    candidates = [_model_to_candidate(item) for item in request.knowledge_items]

    # Forcer le document_id des source_references pour la cohérence
    doc_id_for_source = str(request.document_id) if request.document_id is not None else None
    for c in candidates:
        if not c.source_reference.document_id:
            c.source_reference.document_id = doc_id_for_source
        if not c.source_reference.chunk_id and request.chunk_id is not None:
            c.source_reference.chunk_id = str(request.chunk_id)

    # Connexion et sauvegarde (DictCursor requis par save_knowledge_candidates_to_db)
    try:
        conn = await _get_dict_cursor_connection()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de connexion à la base: {str(e)}",
        )

    try:
        # 1. Créer / récupérer la ressource knowledge_resources
        resource_id = await get_or_create_knowledge_resource(
            conn,
            title=resource_title,
            uri=request.resource_uri,
            resource_type=request.resource_type,
        )

        # 2. Sauvegarder les candidats (knowledge_items + relations)
        saved_ids = await save_knowledge_candidates_to_db(
            candidates,
            conn,
            resource_id=resource_id,
            document_id=doc_id_for_source,
        )

        # 3. Récupérer le détail par knowledge_item (entités/thèmes/sources liées)
        results: List[KnowledgeSaveResult] = []
        for kid, candidate in zip(saved_ids, candidates):
            entities_count = len(candidate.entities)
            themes_count = len(candidate.themes)
            source_saved = bool(candidate.source_reference and candidate.source_reference.excerpt)
            results.append(KnowledgeSaveResult(
                knowledge_id=kid,
                proposition=candidate.proposition,
                entities_count=entities_count,
                themes_count=themes_count,
                source_saved=source_saved,
            ))

        await conn.close()

        return KnowledgeSaveResponse(
            success=True,
            resource_id=resource_id,
            saved_ids=saved_ids,
            results=results,
            count=len(saved_ids),
            message=f"{len(saved_ids)} knowledge_items sauvegardés pour la ressource "
                    f"'{resource_title}' (resource_id={resource_id})",
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erreur lors de la sauvegarde des knowledge_items: {e}")
        try:
            await conn.close()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la sauvegarde: {str(e)}",
        )


@router.get(
    "/items",
    summary="Liste les knowledge_items en base",
    description="Retourne les knowledge_items déjà sauvegardés (table knowledge_items) avec leurs entités et thèmes associés, filtrables par resource_id (knowledge_sources).",
)
async def list_knowledge_items(
    resource_id: Optional[int] = None,
    limit: int = Query(default=100, ge=1, le=500),
):

    try:
        async with await get_db_connection() as conn:
            items = await get_knowledge_items(conn, resource_id=resource_id, limit=limit)

            return JSONResponse(content={
                "knowledge_items": items,
                "count": len(items),
                "resource_id_filter": resource_id,
            })
    except Exception as e:
        print(f"Erreur lors de la liste des knowledge_items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}",
        )
