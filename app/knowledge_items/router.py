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
from typing import Optional, List, Dict, Any

import aiomysql
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from database.database import (
    get_db_connection,
    get_all_text_chunks,
    get_chunk_by_id,
    get_resource_basic_metadata,
    DB_CONFIG,
    VALID_TEXT_RESOURCE_ID,
)


async def _get_dict_cursor_connection():
    """Ouvre une connexion MySQL avec DictCursor.

    Requis car save_knowledge_candidates_to_db accède aux résultats par nom
    de colonne (result['id']). get_db_connection() retourne un curseur tuple.
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
    KnowledgeItemSchema,
)

from .models import (
    KnowledgeGenerationRequest,
    KnowledgeGenerationResponse,
    KnowledgeSaveRequest,
    KnowledgeSaveResponse,
    KnowledgeSaveResult,
    KnowledgeItemModel,
    EntityCandidateModel,
    ThemeCandidateModel,
    SourceReferenceModel,
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
    documents_info = []
    async with await get_db_connection() as conn:
        for resource_id in VALID_TEXT_RESOURCE_ID:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id FROM text_documents "
                    "WHERE source_type = 'pdf' AND source_id = %s LIMIT 1",
                    (str(resource_id),),
                )
                result = await cur.fetchone()
                document_id = result[0] if result else None

            if document_id:
                metadata = await get_resource_basic_metadata(conn, resource_id)
                title = metadata.get("title") or f"Document {resource_id}"
                documents_info.append({
                    "document_id": document_id,
                    "resource_id": resource_id,
                    "title": title,
                })

    return JSONResponse(content={
        "valid_documents": VALID_TEXT_RESOURCE_ID,
        "documents": documents_info,
        "count": len(documents_info),
        "description": "Documents avec extracted_text valide et vérifié",
    })


@router.get(
    "/documents/{document_id}/chunks",
    summary="Liste les chunks d'un document",
    description="Retourne tous les chunks d'un document avec leur contenu pour permettre "
                "la sélection d'un chunk précis avant la génération de knowledge_items.",
)
async def get_document_chunks(document_id: int):
    """Récupère tous les chunks d'un document avec leur contenu."""
    try:
        conn = await get_db_connection()
        chunks = await get_all_text_chunks(conn, document_id)
        await conn.close()
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des chunks: {str(e)}",
        )

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Aucun chunk trouvé pour le document {document_id}",
        )

    return JSONResponse(content={
        "document_id": document_id,
        "chunks": chunks,
        "count": len(chunks),
    })


@router.get(
    "/chunks/{chunk_id}",
    summary="Récupère un chunk précis",
    description="Retourne le contenu et les métadonnées d'un chunk précis (text_chunks.id).",
)
async def get_chunk(chunk_id: int):
    """Récupère un chunk spécifique par son ID."""
    try:
        conn = await get_db_connection()
        chunk = await get_chunk_by_id(conn, chunk_id)
        await conn.close()
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
        conn = await get_db_connection()
        chunk = await get_chunk_by_id(conn, request.chunk_id)
        await conn.close()
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
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM knowledge_resources WHERE title = %s ORDER BY id DESC LIMIT 1",
                (resource_title[:500],),
            )
            row = await cur.fetchone()
            if row:
                resource_id = row[0]
            else:
                await cur.execute(
                    "INSERT INTO knowledge_resources (title, uri, resource_type, created_at) "
                    "VALUES (%s, %s, %s, NOW())",
                    (
                        resource_title[:500],
                        request.resource_uri[:1000] if request.resource_uri else None,
                        request.resource_type[:100],
                    ),
                )
                resource_id = cur.lastrowid
                await conn.commit()

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
    description="Retourne les knowledge_items déjà sauvegardés (table knowledge_items) avec "
                "leurs entités et thèmes associés, filtrables par resource_id (knowledge_sources).",
)
async def list_knowledge_items(
    resource_id: Optional[int] = None,
    limit: int = Field(default=100, ge=1, le=500),
):
    """Liste les knowledge_items existants en base."""
    try:
        conn = await get_db_connection()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de connexion à la base: {str(e)}",
        )

    try:
        async with conn.cursor() as cur:
            if resource_id is not None:
                await cur.execute(
                    """
                    SELECT DISTINCT ki.id, ki.proposition, ki.summary, ki.is_verified,
                           ki.verification_notes, ki.created_at, ki.updated_at
                    FROM knowledge_items ki
                    LEFT JOIN knowledge_sources ks ON ks.knowledge_id = ki.id
                    WHERE ks.resource_id = %s
                    ORDER BY ki.created_at DESC
                    LIMIT %s
                    """,
                    (resource_id, limit),
                )
            else:
                await cur.execute(
                    """
                    SELECT id, proposition, summary, is_verified, verification_notes,
                           created_at, updated_at
                    FROM knowledge_items
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            rows = await cur.fetchall()

            items = []
            for row in rows:
                kid = row[0]
                # Entités liées
                await cur.execute(
                    """
                    SELECT e.name, e.type, kie.relevance
                    FROM knowledge_item_entities kie
                    JOIN entities e ON e.id = kie.entity_id
                    WHERE kie.knowledge_id = %s
                    """,
                    (kid,),
                )
                entity_rows = await cur.fetchall()
                entities = [
                    {"name": er[0], "type": er[1], "relevance": float(er[2]) if er[2] is not None else 1.0}
                    for er in entity_rows
                ]

                # Thèmes liés
                await cur.execute(
                    """
                    SELECT t.name, kit.relevance
                    FROM knowledge_item_themes kit
                    JOIN themes t ON t.id = kit.theme_id
                    WHERE kit.knowledge_id = %s
                    """,
                    (kid,),
                )
                theme_rows = await cur.fetchall()
                themes = [
                    {"name": tr[0], "relevance": float(tr[1]) if tr[1] is not None else 1.0}
                    for tr in theme_rows
                ]

                items.append({
                    "id": kid,
                    "proposition": row[1],
                    "summary": row[2],
                    "is_verified": bool(row[3]) if row[3] is not None else False,
                    "verification_notes": row[4],
                    "created_at": row[5].isoformat() if row[5] else None,
                    "updated_at": row[6].isoformat() if row[6] else None,
                    "entities": entities,
                    "themes": themes,
                })

        await conn.close()
        return JSONResponse(content={
            "knowledge_items": items,
            "count": len(items),
            "resource_id_filter": resource_id,
        })
    except Exception as e:
        print(f"Erreur lors de la liste des knowledge_items: {e}")
        try:
            await conn.close()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}",
        )
