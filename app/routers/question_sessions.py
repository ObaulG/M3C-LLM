"""
Router FastAPI pour la gestion des sessions de questions.

Ce router permet de:
- Créer, lire, mettre à jour et supprimer des sessions de questions
- Ajouter/supprimer des questions dans une session
- Réorganiser les questions dans une session
- Rechercher des questions par langage naturel (RAG)

Les sessions sont distinctes des sessions utilisateur (stockées dans la table `sessions`).
"""

from fastapi import APIRouter, HTTPException, Request, Depends, status
from typing import List, Optional
from pydantic import BaseModel

from database.database import (
    get_db_connection,
    create_question_session,
    update_question_session,
    delete_question_session,
    get_question_sessions,
    get_question_session_by_id,
    add_questions_to_session,
    update_session_questions_order,
    remove_questions_from_session,
    validate_question_ids_exist,
    search_questions_in_qdrant,
    generate_question_embedding,
    MISTRAL_EMBED_MODEL,
    MISTRAL_EMBED_DIMENSION,
    QUESTIONS_COLLECTION_PREFIX
)
import auth

router = APIRouter(prefix="/api/question-sessions", tags=["Question Sessions"])

# Rôles autorisés à éditer les sessions
ALLOWED_ROLES = ["global_admin", "admin", "expert"]


# ============================================================================
# MODÈLES PYDANTIC
# ============================================================================

class QuestionSessionCreate(BaseModel):
    """Modèle pour la création d'une session de questions."""
    title: str
    description: str = ""
    document_id: int
    question_ids: List[int] = []


class QuestionSessionUpdate(BaseModel):
    """Modèle pour la mise à jour d'une session de questions."""
    title: Optional[str] = None
    description: Optional[str] = None
    question_ids: Optional[List[int]] = None  # Nouvelle liste ordonnée


class QuestionSessionResponse(BaseModel):
    """Modèle de réponse pour une session de questions."""
    session_id: int
    title: str
    description: str
    document_id: int
    created_by: Optional[int]
    created_at: str
    updated_at: str
    questions: List[dict]  # Liste de {question_id, content, order_index}


class QuestionSearchRequest(BaseModel):
    """Modèle pour la recherche de questions par langage naturel."""
    query: str
    k: int = 5
    document_id: Optional[int] = None
    page: Optional[int] = None
    keyword: Optional[str] = None


# ============================================================================
# FONCTIONS D'AUTHENTIFICATION
# ============================================================================

async def get_current_user_with_roles(request: Request):
    """
    Récupère l'utilisateur courant (connecté ou anonyme).
    """
    user_id = auth.user_id_from_authorization(request.headers.get("authorization"))
    if user_id is None:
        user_id = auth.user_id_from_token(request.cookies.get("m3c_api_key"))
    user = await auth.get_user_by_id(user_id) if user_id is not None else None
    if not user or not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user


async def verify_user_can_edit_sessions(user: dict = Depends(get_current_user_with_roles)):
    """
    Vérifie que l'utilisateur a le droit d'éditer les sessions.
    Seuls les global_admin, admin et expert peuvent éditer.
    """
    role = (user.get("role") or "").strip().lower()
    if role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Seuls les {', '.join(ALLOWED_ROLES)} peuvent éditer les sessions. "
                f"Utilisateur #{user.get('user_id')} connecté avec le rôle '{user.get('role')}'."
            )
        )
    return user


# ============================================================================
# ROUTES POUR LA GESTION DES SESSIONS
# ============================================================================

@router.post("/", response_model=QuestionSessionResponse)
async def create_question_session_endpoint(
    request: QuestionSessionCreate,
    user: dict = Depends(verify_user_can_edit_sessions)
):
    """
    Crée une nouvelle session de questions.
    Réservé aux utilisateurs avec rôle global_admin, admin ou expert.
    """
    created_by = user.user_id

    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            # Vérifier que le document existe
            await cur.execute(
                "SELECT id FROM text_documents WHERE id = %s",
                (request.document_id,)
            )
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Document non trouvé")

        # Vérifier que toutes les questions existent
        if request.question_ids:
            if not await validate_question_ids_exist(request.question_ids):
                raise HTTPException(status_code=400, detail="Une ou plusieurs questions n'existent pas")

        # Créer la session
        session_id = await create_question_session(
            request.title,
            request.description,
            request.document_id,
            created_by
        )

        # Ajouter les questions si fournies
        if request.question_ids:
            await add_questions_to_session(session_id, request.question_ids)

        # Récupérer la session créée
        session = await get_question_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=500, detail="Erreur lors de la création de la session")

        return QuestionSessionResponse(**session)


@router.get("/document/{document_id}", response_model=List[QuestionSessionResponse])
async def get_sessions_by_document(
    document_id: int,
    user: dict = Depends(get_current_user_with_roles)  # Lecture autorisée pour tous les connectés
):
    """
    Récupère toutes les sessions pour un document.
    Accessible à tous les utilisateurs connectés.
    """
    sessions = await get_question_sessions(document_id=document_id)
    # Pour chaque session, récupérer les questions
    full_sessions = []
    for session in sessions:
        full_session = await get_question_session_by_id(session["session_id"])
        full_sessions.append(QuestionSessionResponse(**full_session))
    return full_sessions


@router.get("/{session_id}", response_model=QuestionSessionResponse)
async def get_question_session(
    session_id: int,
    user: dict = Depends(get_current_user_with_roles)
):
    """
    Récupère une session par son ID.
    Accessible à tous les utilisateurs connectés.
    """
    session = await get_question_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    return QuestionSessionResponse(**session)


@router.put("/{session_id}", response_model=QuestionSessionResponse)
async def update_question_session_endpoint(
    session_id: int,
    request: QuestionSessionUpdate,
    user: dict = Depends(verify_user_can_edit_sessions)
):
    """
    Met à jour une session (titre, description, ordre des questions).
    Réservé aux global_admin, admin, expert.
    """
    # Vérifier que la session existe
    session = await get_question_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")

    # Mettre à jour le titre/description
    if request.title is not None or request.description is not None:
        await update_question_session(
            session_id,
            request.title,
            request.description
        )

    # Mettre à jour l'ordre des questions si fourni
    if request.question_ids is not None:
        # Vérifier que toutes les questions existent
        if not await validate_question_ids_exist(request.question_ids):
            raise HTTPException(status_code=400, detail="Une ou plusieurs questions n'existent pas")

        # Mettre à jour l'ordre
        if not await update_session_questions_order(session_id, request.question_ids):
            raise HTTPException(status_code=400, detail="Erreur lors de la mise à jour de l'ordre des questions")

    # Récupérer la session mise à jour
    updated_session = await get_question_session_by_id(session_id)
    return QuestionSessionResponse(**updated_session)


@router.delete("/{session_id}")
async def delete_question_session_endpoint(
    session_id: int,
    user: dict = Depends(verify_user_can_edit_sessions)
):
    """
    Supprime une session.
    Réservé aux global_admin, admin, expert.
    """
    if not await get_question_session_by_id(session_id):
        raise HTTPException(status_code=404, detail="Session non trouvée")
    await delete_question_session(session_id)
    return {"message": "Session supprimée avec succès"}


@router.post("/{session_id}/questions", response_model=QuestionSessionResponse)
async def add_questions_to_session_endpoint(
    session_id: int,
    question_ids: List[int],
    user: dict = Depends(verify_user_can_edit_sessions)
):
    """
    Ajoute des questions à une session.
    Réservé aux global_admin, admin, expert.
    """
    # Vérifier que la session existe
    if not await get_question_session_by_id(session_id):
        raise HTTPException(status_code=404, detail="Session non trouvée")

    # Vérifier que toutes les questions existent
    if not await validate_question_ids_exist(question_ids):
        raise HTTPException(status_code=400, detail="Une ou plusieurs questions n'existent pas")

    # Ajouter les questions
    await add_questions_to_session(session_id, question_ids)

    # Récupérer la session mise à jour
    session = await get_question_session_by_id(session_id)
    return QuestionSessionResponse(**session)


@router.delete("/{session_id}/questions")
async def remove_questions_from_session_endpoint(
    session_id: int,
    question_ids: List[int],
    user: dict = Depends(verify_user_can_edit_sessions)
):
    """
    Supprime des questions d'une session.
    Réservé aux global_admin, admin, expert.
    """
    # Vérifier que la session existe
    if not await get_question_session_by_id(session_id):
        raise HTTPException(status_code=404, detail="Session non trouvée")

    await remove_questions_from_session(session_id, question_ids)
    return {"message": f"{len(question_ids)} questions supprimées de la session"}


# ============================================================================
# ROUTE POUR LA RECHERCHE DE QUESTIONS PAR RAG
# ============================================================================

@router.post("/search-questions", response_model=List[dict])
async def search_questions_by_natural_language(
    request: QuestionSearchRequest,
    user: dict = Depends(get_current_user_with_roles)  # Authentification requise
):
    """
    Recherche des questions similaires à une requête en langage naturel.
    Utilise Qdrant pour la recherche (plus rapide que la base de données).
    Limité au document sélectionné (si document_id est fourni).
    
    Accessible à tous les utilisateurs connectés.
    """
    collection_name = f"{QUESTIONS_COLLECTION_PREFIX}-{MISTRAL_EMBED_MODEL}-{MISTRAL_EMBED_DIMENSION}"

    # Générer l'embedding de la requête
    try:
        query_embedding = await generate_question_embedding(request.query)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la génération de l'embedding: {str(e)}"
        )

    # Rechercher dans Qdrant
    results = await search_questions_in_qdrant(
        query_embedding=query_embedding,
        k=request.k,
        document_id=request.document_id,
        collection_name=collection_name
    )

    if not results:
        return []

    # Filtrer par mot-clé si fourni
    if request.keyword:
        keyword_lower = request.keyword.lower()
        results = [
            r for r in results
            if keyword_lower in r.get("content", "").lower()
        ]

    # Filtrer par page si fourni
    if request.page is not None:
        async with await get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT DISTINCT tq.question_id
                    FROM text_questions tq
                    JOIN text_question_chunks tqc ON tq.question_id = tqc.question_id
                    JOIN text_chunks tc ON tqc.chunk_id = tc.id
                    WHERE tc.num_page = %s
                    """,
                    (request.page,)
                )
                page_question_ids = {row[0] for row in await cur.fetchall()}
                results = [r for r in results if r["question_id"] in page_question_ids]

    return results
