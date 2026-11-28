"""
Router FastAPI pour la gestion des sessions de questions.

Ce router permet de:
- Créer, lire, mettre à jour et supprimer des sessions de questions
- Ajouter/supprimer des questions dans une session
- Réorganiser les questions dans une session
- Rechercher des questions par langage naturel (RAG)

Les sessions sont distinctes des sessions utilisateur (stockées dans la table `sessions`).
"""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Depends, status
from typing import List, Optional
from pydantic import BaseModel, Field

from database.database import (
    get_db_connection,
    get_questions_by_document_id,
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
    create_question_from_session_proposal,
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

class NewQuestionProposal(BaseModel):
    """Nouvelle question proposée par l'agent lors de la création automatique d'une session.

    Elle n'est sauvegardée en BDD que lorsque l'utilisateur confirme la session :
    l'agent lui-même ne persiste jamais rien.
    """
    question: str = Field(..., min_length=1, description="Formulation de la question proposée")
    answer: str = Field("", description="Réponse de référence proposée")
    source_question_id: Optional[int] = Field(None, description="Question existante dont la proposition s'inspire (type 'adapted')")


class QuestionSessionCreate(BaseModel):
    """Modèle pour la création d'une session de questions."""
    title: str
    description: str = ""
    document_id: int
    question_ids: List[int] = []
    new_questions: List[NewQuestionProposal] = []  # Propositions à créer à la sauvegarde
    model: Optional[str] = None  # Modèle utilisé pour générer les propositions (traçabilité)


class QuestionSessionUpdate(BaseModel):
    """Modèle pour la mise à jour d'une session de questions."""
    title: Optional[str] = None
    description: Optional[str] = None
    question_ids: Optional[List[int]] = None  # Nouvelle liste ordonnée
    new_questions: Optional[List[NewQuestionProposal]] = None  # Propositions à créer à la sauvegarde
    model: Optional[str] = None  # Modèle utilisé pour générer les propositions (traçabilité)


class QuestionSessionResponse(BaseModel):
    """Modèle de réponse pour une session de questions."""
    session_id: int
    title: str
    description: str
    document_id: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    questions: List[dict]  # Liste de {question_id, content, order_index}


class QuestionSearchRequest(BaseModel):
    """Modèle pour la recherche de questions par langage naturel."""
    query: str
    k: int = 5
    document_id: Optional[int] = None
    page: Optional[int] = None
    keyword: Optional[str] = None


class SessionQuestionProposalItem(BaseModel):
    """Une proposition de question retournée par l'agent (ou renvoyée lors d'une négociation)."""
    question: str
    answer: str = ""
    proposal_type: str = Field("new", description="existing | adapted | new")
    source_question_id: Optional[int] = None
    rationale: Optional[str] = None


class SessionQuestionGenerationRequest(BaseModel):
    """Requête de génération automatique de propositions de questions pour une session.

    L'agent ne sauvegarde rien en BDD : il retourne uniquement des propositions.
    En cas de négociation, current_proposals contient la liste des propositions
    retenues (ajoutée au prompt) et negotiation_instructions les consignes de l'utilisateur.
    """
    instructions: str = Field(..., min_length=3, description="Instructions du médiateur : ce qu'on cherche à présenter au visiteur durant la session")
    document_id: int
    num_questions: int = Field(5, ge=1, le=20)
    model: Optional[str] = Field("mistral-small-2603", description="Modèle LLM (avec préfixe provider/ éventuel)")
    current_proposals: Optional[List[SessionQuestionProposalItem]] = None
    negotiation_instructions: Optional[str] = None


class SessionQuestionGenerationResponse(BaseModel):
    """Propositions de questions pour la session (aucune sauvegarde en BDD)."""
    proposals: List[SessionQuestionProposalItem]
    model_used: str
    generation_time: float
    candidates_count: int


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
    created_by = user["user_id"]

    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            # Vérifier que le document existe
            await cur.execute(
                "SELECT id FROM text_documents WHERE id = %s",
                (request.document_id,)
            )
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Document non trouvé")

        # Créer les nouvelles questions proposées (sauvegarde uniquement à la confirmation)
        question_ids = list(request.question_ids)
        for new_q in request.new_questions:
            new_id = await create_question_from_session_proposal(
                content=new_q.question,
                answer=new_q.answer or None,
                document_id=request.document_id,
                created_by=created_by,
                source_question_id=new_q.source_question_id,
                model=request.model or ""
            )
            question_ids.append(new_id)

        # Vérifier que toutes les questions existent
        if question_ids:
            if not await validate_question_ids_exist(question_ids):
                raise HTTPException(status_code=400, detail="Une ou plusieurs questions n'existent pas")

        # Créer la session
        session_id = await create_question_session(
            request.title,
            request.description,
            request.document_id,
            created_by
        )

        # Ajouter les questions si fournies
        if question_ids:
            await add_questions_to_session(session_id, question_ids)

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

    # Créer les nouvelles questions proposées (sauvegarde uniquement à la confirmation)
    new_question_ids = []
    if request.new_questions:
        for new_q in request.new_questions:
            new_id = await create_question_from_session_proposal(
                content=new_q.question,
                answer=new_q.answer or None,
                document_id=session["document_id"],
                created_by=user["user_id"],
                source_question_id=new_q.source_question_id,
                model=request.model or ""
            )
            new_question_ids.append(new_id)

    # Mettre à jour l'ordre des questions si fourni
    if request.question_ids is not None:
        all_question_ids = list(request.question_ids) + new_question_ids

        # Vérifier que toutes les questions existent
        if not await validate_question_ids_exist(all_question_ids):
            raise HTTPException(status_code=400, detail="Une ou plusieurs questions n'existent pas")

        # Ajouter les nouvelles questions à la session avant de réordonner
        if new_question_ids:
            await add_questions_to_session(session_id, new_question_ids)

        # Mettre à jour l'ordre
        if not await update_session_questions_order(session_id, all_question_ids):
            raise HTTPException(status_code=400, detail="Erreur lors de la mise à jour de l'ordre des questions")
    elif new_question_ids:
        # Pas de réordonnancement demandé : ajouter les nouvelles questions à la fin
        await add_questions_to_session(session_id, new_question_ids)

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


# ============================================================================
# ROUTE POUR LA GÉNÉRATION AUTOMATIQUE DE PROPOSITIONS DE QUESTIONS (SESSION)
# ============================================================================

async def _fetch_question_details(question_ids: List[int]) -> dict:
    """Récupère le contenu, la page et la réponse de référence des questions demandées."""
    details = {}
    if not question_ids:
        return details
    placeholders = ",".join(["%s"] * len(question_ids))
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(f"""
                SELECT q.question_id, q.content, q.status, q.difficulty_level, tc.num_page
                FROM text_questions q
                LEFT JOIN text_question_chunks qc ON qc.question_id = q.question_id
                LEFT JOIN text_chunks tc ON tc.id = qc.chunk_id
                WHERE q.question_id IN ({placeholders})
                GROUP BY q.question_id, q.content, q.status, q.difficulty_level, tc.num_page
            """, tuple(question_ids))
            rows = await cur.fetchall()
            await cur.execute(f"""
                SELECT question_id, content FROM text_question_answers
                WHERE question_id IN ({placeholders})
                ORDER BY is_correct DESC, answer_id ASC
            """, tuple(question_ids))
            answer_rows = await cur.fetchall()

    answers_by_qid = {}
    for qid, content in answer_rows:
        answers_by_qid.setdefault(qid, content)
    for row in rows:
        qid, content, status, difficulty, num_page = row
        details[qid] = {
            "content": content,
            "status": status,
            "difficulty_level": difficulty,
            "num_page": num_page,
            "main_answer": answers_by_qid.get(qid),
        }
    return details


async def _get_session_candidate_questions(document_id: int, instructions: str, k: int) -> List[dict]:
    """
    Récupère les questions candidates du document pour composer la session :
    recherche sémantique dans Qdrant à partir des instructions du médiateur,
    avec repli sur les questions de la base si Qdrant ne retourne rien.
    Lecture seule : aucune sauvegarde n'est effectuée.
    """
    collection_name = f"{QUESTIONS_COLLECTION_PREFIX}-{MISTRAL_EMBED_MODEL}-{MISTRAL_EMBED_DIMENSION}"
    results = []
    try:
        query_embedding = await generate_question_embedding(instructions)
        results = await search_questions_in_qdrant(
            query_embedding=query_embedding,
            k=k,
            document_id=document_id,
            collection_name=collection_name
        )
    except Exception as e:
        print(f"Erreur lors de la recherche Qdrant des questions candidates: {e}")

    if results:
        candidate_ids = [r["question_id"] for r in results]
        similarity_by_id = {r["question_id"]: r.get("similarity") for r in results}
        details = await _fetch_question_details(candidate_ids)
        candidates = [
            {
                "question_id": qid,
                "content": det["content"],
                "main_answer": det.get("main_answer"),
                "num_page": det.get("num_page"),
                "similarity": similarity_by_id.get(qid),
            }
            for qid, det in details.items()
        ]
        candidates.sort(key=lambda c: c["similarity"] if c["similarity"] is not None else 0.0, reverse=True)
        return candidates

    # Repli sur la base de données si Qdrant est vide ou indisponible
    async with await get_db_connection() as conn:
        questions = await get_questions_by_document_id(str(document_id), conn, include_answers=True, nb_limit=k)
    candidates = []
    for q in questions:
        answers = q.get("answers", [])
        main_answer = next((a["content"] for a in answers if a.get("is_correct")), None)
        if main_answer is None and answers:
            main_answer = answers[0]["content"]
        candidates.append({
            "question_id": q["question_id"],
            "content": q["content"],
            "main_answer": main_answer,
            "num_page": q.get("num_page"),
            "similarity": None,
        })
    return candidates


@router.post("/generate-questions", response_model=SessionQuestionGenerationResponse)
async def generate_session_question_proposals(
    request: SessionQuestionGenerationRequest,
    user: dict = Depends(verify_user_can_edit_sessions)
):
    """
    Génère des propositions de questions pour une session à partir des instructions
    du médiateur culturel/scientifique.

    L'agent sélectionne en priorité des questions existantes correspondant à la
    demande, sinon adapte une question existante (formulation/réponse modifiées),
    sinon crée directement une nouvelle paire question/réponse.

    IMPORTANT : aucune sauvegarde en BDD — l'endpoint retourne uniquement des
    propositions. Lors d'une négociation, la liste des propositions retenues
    (current_proposals) est ajoutée au prompt avec les consignes
    (negotiation_instructions), et l'agent renvoie une nouvelle liste ajustée.
    """
    import time
    from agents.session_question_agent import (
        get_session_question_agent,
        SessionQuestionGenerationInput,
    )

    start_time = time.time()

    # Vérifier que le document existe
    async with await get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM text_documents WHERE id = %s",
                (request.document_id,)
            )
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Document non trouvé")

    # Questions candidates du document (RAG sur les instructions, repli BDD)
    k = max(request.num_questions * 3, 10)
    candidates = await _get_session_candidate_questions(request.document_id, request.instructions, k)

    # Provider et modèle
    model_name = request.model or "mistral-small-2603"
    provider, model = tuple(model_name.split("/")) if "/" in model_name else ("mistral", model_name)

    agent = get_session_question_agent(model=model, provider=provider, async_mode=True)
    input_data = SessionQuestionGenerationInput(
        mediator_instructions=request.instructions,
        num_questions=request.num_questions,
        candidate_questions=[
            {
                "question_id": c["question_id"],
                "content": c["content"],
                "main_answer": c.get("main_answer"),
                "num_page": c.get("num_page"),
                "similarity": c.get("similarity"),
            }
            for c in candidates
        ],
        current_proposals=[p.model_dump() for p in request.current_proposals] if request.current_proposals else None,
        negotiation_instructions=request.negotiation_instructions or None,
    )

    try:
        response = await agent.run_async(input_data)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la génération des propositions par l'agent: {str(e)}"
        )

    # Normaliser les propositions : un "existing" doit référencer un candidat connu
    candidate_by_id = {c["question_id"]: c for c in candidates}
    proposals = []
    seen_existing = set()
    for p in response.proposals:
        if len(proposals) >= request.num_questions:
            break
        if not p.question or not p.question.strip():
            continue
        ptype = p.proposal_type
        src = p.source_question_id
        if src is not None and src not in candidate_by_id:
            src = None
        if ptype == "existing" and src is None:
            ptype = "new"
        if ptype == "existing" and src in seen_existing:
            ptype = "adapted"
        if ptype == "existing":
            seen_existing.add(src)
            cand = candidate_by_id[src]
            proposals.append(SessionQuestionProposalItem(
                question=cand["content"],
                answer=cand.get("main_answer") or "",
                proposal_type="existing",
                source_question_id=src,
                rationale=p.rationale or "Question existante correspondant à la demande."
            ))
        else:
            proposals.append(SessionQuestionProposalItem(
                question=p.question.strip(),
                answer=(p.answer or "").strip(),
                proposal_type=ptype,
                source_question_id=src,
                rationale=p.rationale or None,
            ))

    return SessionQuestionGenerationResponse(
        proposals=proposals[:request.num_questions],
        model_used=model_name,
        generation_time=time.time() - start_time,
        candidates_count=len(candidates),
    )
