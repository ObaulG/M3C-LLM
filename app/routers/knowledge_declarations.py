"""Router FastAPI pour les dclarations de connaissance des visiteurs.

Permet aux visiteurs (connects ou anonymes) de dclarer leur familiarit
avec des lments de connaissance regroups par thme (schma
user_knowledge_model.sql). Chaque dclaration cre une observation
dclarative et met  jour l'tat de connaissance de l'utilisateur.

Routes :
- GET  /api/knowledge-declarations/themes           (thmes avec lments de connaissance)
- GET  /api/knowledge-declarations/themes/{id}      (lments d'un thme + tats de l'utilisateur)
- POST /api/knowledge-declarations/declarations     (enregistrer une dclaration)
"""
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Cookie, HTTPException, Query, status
from pydantic import BaseModel, Field

import auth
from database.database import (
    get_db_connection,
    get_knowledge_items_by_theme,
    get_user_knowledge_states_for_items,
    record_knowledge_declaration,
    record_document_prior_read_declaration,
)

router = APIRouter(prefix="/api/knowledge-declarations", tags=["Knowledge Declarations"])

DeclaredStatus = Literal["unknown", "encountered", "developing", "demonstrated"]


class ThemeOption(BaseModel):
    theme_id: int = Field(..., description="Identifiant du thme (themes.id)")
    theme_name: str = Field(..., description="Nom du thme")
    theme_description: Optional[str] = Field(None, description="Description du thme")
    knowledge_items_count: int = Field(..., description="Nombre d'lments de connaissance associs au thme")


class KnowledgeItemOption(BaseModel):
    knowledge_id: int = Field(..., description="Identifiant de l'lment de connaissance")
    proposition: str = Field(..., description="Proposition formulate et vrifiable")
    summary: Optional[str] = Field(None, description="Rsum de la proposition")
    relevance: Optional[float] = Field(None, description="Pertinence du thme pour cet lment")
    user_status: Optional[DeclaredStatus] = Field(None, description="tat de connaissance actuel de l'utilisateur (si connect)")
    user_score: Optional[float] = Field(None, description="Score de matrise actuel (si connect)")


class KnowledgeDeclarationRequest(BaseModel):
    theme_id: int = Field(..., description="Identifiant du thme dclar", ge=1)
    knowledge_id: int = Field(..., description="Identifiant de l'lment de connaissance dclar", ge=1)
    declared_status: DeclaredStatus = Field(..., description="Niveau de familiarit dclar par le visiteur")
    anonymous_id: Optional[str] = Field(None, description="Identifiant anonyme persistant (localStorage), ignor si l'utilisateur est connect", max_length=100)
    metadata: Optional[Dict] = Field(None, description="Mtadonnes supplmentaires (page d'origine, etc.)")


class KnowledgeDeclarationResponse(BaseModel):
    observation_id: int = Field(..., description="Identifiant de l'observation dclarative cre")
    knowledge_id: int = Field(..., description="Identifiant de l'lment de connaissance dclar")
    declared_status: DeclaredStatus = Field(..., description="Statut dclar enregistr")
    user_identifier: str = Field(..., description="Identifiant utilis pour l'observation (user_id ou anonyme)")


def _resolve_user_identifier(
    m3c_api_key: Optional[str],
    authorization: Optional[str],
    anonymous_id: Optional[str],
) -> tuple[Optional[int], Optional[str]]:
    """Retourne (user_id connect, identifiant pour les observations)."""
    user_id = auth.user_id_from_token(m3c_api_key)
    if user_id is None:
        user_id = auth.user_id_from_authorization(authorization)
    if user_id is not None:
        return user_id, str(user_id)
    if anonymous_id:
        return None, anonymous_id
    return None, None


class DocumentPriorReadRequest(BaseModel):
    resource_id: int = Field(..., description="Identifiant du document (table value, resource_id)", ge=1)
    already_read: bool = Field(..., description="True si le visiteur declare avoir deja consulte ou lu le document avant sa visite")
    anonymous_id: Optional[str] = Field(None, description="Identifiant anonyme persistant (localStorage), ignore si l'utilisateur est connecte", max_length=100)
    metadata: Optional[Dict] = Field(None, description="Metadonnees supplementaires (page d'origine, etc.)")


class DocumentPriorReadResponse(BaseModel):
    observation_id: int = Field(..., description="Identifiant de l'observation declarative creee")
    resource_id: int = Field(..., description="Identifiant du document concerne")
    already_read: bool = Field(..., description="Valeur declaree enregistree")


@router.post(
    "/document-prior-read",
    response_model=DocumentPriorReadResponse,
    summary="Enregistre la declaration de lecture prealable d'un document",
)
async def declare_document_prior_read(
    request: DocumentPriorReadRequest,
    m3c_api_key: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = None,
):
    """
    Enregistre la reponse d'un visiteur indiquant s'il a deja consulte ou lu
    un document avant sa visite. Visiteurs connectes et anonymes acceptes.
    Le bouton Fermer du widget n'envoie aucun appel a cette route.
    """
    user_id, obs_user_id = _resolve_user_identifier(
        m3c_api_key, authorization, request.anonymous_id
    )
    if obs_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun identifiant disponible : veuillez vous connecter ou fournir un anonymous_id.",
        )

    async with await get_db_connection() as conn:
        observation_id = await record_document_prior_read_declaration(
            conn,
            user_id=obs_user_id,
            resource_id=request.resource_id,
            already_read=request.already_read,
            anonymous_id=request.anonymous_id if user_id is None else None,
            metadata=request.metadata,
        )

    if observation_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'enregistrement de la declaration.",
        )

    return DocumentPriorReadResponse(
        observation_id=observation_id,
        resource_id=request.resource_id,
        already_read=request.already_read,
    )


@router.get(
    "/themes",
    response_model=List[ThemeOption],
    summary="Liste les themes ayant des elements de connaissance",
)
async def list_themes_with_knowledge(
    search: Optional[str] = Query(None, description="Filtre optionnel sur le nom du thme", max_length=200),
    limit: int = Query(50, description="Nombre maximum de thmes retourns", ge=1, le=200),
):
    """
    Liste les thmes prsents dans la base (table themes) qui possdent
    au moins un lment de connaissance associ (knowledge_item_themes).
    """
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            query = """
                SELECT t.id, t.name, t.description, COUNT(kit.knowledge_id) AS knowledge_items_count
                FROM themes t
                JOIN knowledge_item_themes kit ON kit.theme_id = t.id
                JOIN knowledge_items ki ON ki.id = kit.knowledge_id
                """
            params: list = []
            if search:
                query += " WHERE t.name LIKE %s"
                params.append(f"%{search}%")
            query += """
                GROUP BY t.id, t.name, t.description
                ORDER BY t.name
                LIMIT %s
                """
            params.append(limit)
            await cur.execute(query, tuple(params))
            rows = await cur.fetchall()

    return [
        ThemeOption(
            theme_id=row[0],
            theme_name=row[1] or "",
            theme_description=row[2],
            knowledge_items_count=row[3] or 0,
        )
        for row in rows
    ]


@router.get(
    "/themes/{theme_id}",
    response_model=List[KnowledgeItemOption],
    summary="Liste les lments de connaissance d'un thme avec les tats de l'utilisateur",
)
async def list_theme_knowledge_items(
    theme_id: int,
    limit: int = Query(50, description="Nombre maximum d'lments retourns", ge=1, le=200),
    m3c_api_key: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = None,
):
    """
    Liste les lments de connaissance du thme donn. Si l'utilisateur est
    connect, son tat de connaissance actuel est inclus pour chaque lment.
    """
    user_id, obs_user_id = _resolve_user_identifier(m3c_api_key, authorization, None)

    async with await get_db_connection() as conn:
        items = await get_knowledge_items_by_theme(conn, theme_id, limit)
        if not items:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Aucun lment de connaissance trouv pour le thme {theme_id}.",
            )
        states: Dict[int, Dict] = {}
        if obs_user_id:
            states = await get_user_knowledge_states_for_items(
                conn, obs_user_id, [item["id"] for item in items]
            )

    result = []
    for item in items:
        state = states.get(item["id"], {})
        result.append(KnowledgeItemOption(
            knowledge_id=item["id"],
            proposition=item.get("proposition") or "",
            summary=item.get("summary"),
            relevance=item.get("relevance"),
            user_status=state.get("status"),
            user_score=state.get("score"),
        ))
    return result


@router.post(
    "/declarations",
    response_model=KnowledgeDeclarationResponse,
    summary="Enregistre une dclaration de connaissance d'un visiteur",
)
async def declare_knowledge(
    request: KnowledgeDeclarationRequest,
    m3c_api_key: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = None,
):
    """
    Enregistre une dclaration de familiarit d'un visiteur pour un lment
    de connaissance d'un thme. Utilisateurs connects et anonymes acceptes ;
    cre une observation dclarative et met  jour l'tat de connaissance.
    """
    user_id, obs_user_id = _resolve_user_identifier(
        m3c_api_key, authorization, request.anonymous_id
    )
    if obs_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun identifiant disponible : veuillez vous connecter ou fournir un anonymous_id.",
        )

    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT name FROM themes WHERE id = %s", (request.theme_id,))
            row = await cur.fetchone()
            theme_label = row[0] if row else None
        if theme_label is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Thme {request.theme_id} introuvable.",
            )

        items = await get_knowledge_items_by_theme(conn, request.theme_id, limit=1000)
        item = next((it for it in items if it["id"] == request.knowledge_id), None)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"L'lment de connaissance {request.knowledge_id} n'est pas associ au thme {request.theme_id}.",
            )

        observation_id = await record_knowledge_declaration(
            conn,
            user_id=obs_user_id,
            theme_id=request.theme_id,
            theme_name=theme_label,
            knowledge_id=request.knowledge_id,
            knowledge_proposition=item.get("proposition") or "",
            declared_status=request.declared_status,
            anonymous_id=request.anonymous_id if user_id is None else None,
            metadata=request.metadata,
        )

    if observation_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'enregistrement de la dclaration.",
        )

    return KnowledgeDeclarationResponse(
        observation_id=observation_id,
        knowledge_id=request.knowledge_id,
        declared_status=request.declared_status,
        user_identifier=obs_user_id,
    )
