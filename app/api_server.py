import asyncio
import copy
import csv
import json
import logging
import os
import time
import uuid
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from contextlib import asynccontextmanager
from unittest import case
from fastapi import FastAPI, HTTPException, status, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from dotenv import load_dotenv
from starlette.responses import JSONResponse

import database
import auth
from rag_pipeline import RAGPipeline, RetrievalResult, RAGSource
from question_session import (PREMADE_QUESTIONS_BY_DOCUMENT_ID,
                              QuestionSessionManager,
                              EvaluateRequest,
                              UserResponse,
                              SessionStatus,
                              EvaluationResult,
                              from_AgentEvaluationResult_to_EvaluationResult, session_status_to_dict)
from session_csv_logger import log_response_to_csv
from evaluation_logger import log_evaluation_to_csv, get_reference_answers, get_reference_answer
from evaluation_feedback_logger import log_feedback_to_csv
from agents.qa_agent import get_qa_agent
from agents.answer_evaluator_agent import get_evaluator_agent, EvaluateRequestInput, get_final_evaluator_agent, \
    ListAgentEvaluationResult, AgentEvaluationResult
from agents.instructor_factory import MISTRAL_MODELS, GOOGLE_MODELS
from agents.message_evaluator_agent import get_message_type_agent, MessageTypeRequestInput
from database.database import (get_db_connection,
                               get_all_documents,
                               get_questions_by_document_id,
                               get_question_by_id,
                               get_questions_by_ids,
                               get_chunks_by_question_id,
                               get_chunks_by_question_ids,
                               insert_chunk_embeddings_batch_qdrant,
                               insert_chunks,
                               insert_session,
                               VALID_TEXT_RESOURCE_ID, get_pdf_url_for_resource, get_pdf_name_from_resource_id,
                               get_document_id_from_resource_id,
                               M3C_BASE_URL)
from agents.token_monitor import *
from config import DOCUMENTS_PATH
import asyncio
from rag_session import RAGSessionManager, RAGSession, RAGInteraction
if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import torch
import uvicorn

import api_visualization
from api_visualization import router as viz_router, set_rag_pipeline, set_embedding_model
from app.embedders import create_mistral_embedder, get_default_embedder
from app.embedders.router import router as embedders_router

import json
from datetime import datetime

# Import du router d'indexing
from indexing.router import router as indexing_router

# Import du router de génération de questions
from question_answer.router import router as question_answer_router

# Import du router pour l'évaluation des messages
from question_answer.message_evaluator_router import router as message_evaluator_router

# Import du router de génération de knowledge_items
from knowledge_items.router import router as knowledge_items_router

# Import de la fonction de recommandation de questions
from question_answer.services import recommend_questions_for_document, generate_questions_single_answer_for_chunk

# Import du router Solr
from solr.router import router as solr_router

# Charger les variables d'environnement
load_dotenv()
# === MODELS PYDANTIC ===
class QueryRequest(BaseModel):
    """ModÃ¨le de requête pour poser une question"""
    question: str = Field(..., description="Question à poser au chatbot", min_length=1)
    models: List[str] = Field(..., description="ModÃ¨les utilisés pour la génération")
    temperature: Optional[float] = Field(0.7, description="Température du modèle")
    k: int = Field(3, description="Nombre de documents à récupérer", ge=1, le=20)
    use_rag: bool = Field(False, description="Utiliser le RAG pour s'appuyer sur des ressources existantes")
    rag_monodocument_id: Optional[int]= Field(None, description="RAG sur un seul document dont on fournit l'identifiant")
    use_reranking: bool = Field(False, description="Utiliser le reranking pour améliorer les résultats")
    include_quantitative: Optional[bool] = Field(True, description="Inclure les données quantitatives")
    session_id: Optional[str] = Field(None, description="ID de session pour récupérer l'historique des messages")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "",
                "k": 3,
                "model": "mistral-7b",
                "use_reranking": False,
                "include_quantitative": True,
            }
        }
    )
class QueryResponse(BaseModel):
    """ModÃ¨le de réponse à une question"""
    answer: str = Field(..., description="Réponse générée par le chatbot")
    sources: Optional[List[RAGSource]] = Field(
        None,
        description="Sources utilisées pour la réponse dans le cas oÃ¹ le RAG est activé"
    )
    total_time: float = Field(..., description="Temps total de la génération")
    metadata: Dict = Field(..., description="Métadonnées de la requête")
    timestamp: str = Field(..., description="Horodatage de la réponse")

class QueryCompareResponse(BaseModel):
    responses: List[QueryResponse]
    total_time: float = Field(..., description="Temps total de la génération")
    metadata: Dict = Field(..., description="Métadonnées de la requête")
    timestamp: str = Field(..., description="Horodatage de la réponse")

class DocumentResponse(BaseModel):
    """Modèle de réponse pour un document contenant les informations de base"""
    document_id: int = Field(..., description="Identifiant du document (item, ou document_id")
    source_id: Optional[int] = Field(..., description="Identifiant de la ressource pour requêter le pdf")
    file_name: str = Field(..., description="Nom du fichier")
    title: str = Field(..., description="Titre du document")
    author: str = Field(..., description="Auteur du document")
    created_at: str = Field(..., description="Date de création")
    updated_at: str = Field(..., description="Date de mise à jour")
class DocumentsListResponse(BaseModel):
    """ModÃ¨le de réponse pour la liste des documents"""
    documents: List[DocumentResponse] = Field(..., description="Liste des documents")
    count: int = Field(..., description="Nombre total de documents")
    timestamp: str = Field(..., description="Horodatage de la réponse")
class RAGParameters(BaseModel):
    nb_sources: int
    reranking: bool
class LLMCallData(BaseModel):
    model: str
    framework: Optional[str] = Field(None, description="Framework utilisé pour l'appel.")
    input_tokens: Optional[int] = Field(None, description="Nombre de tokens d'entrée.")
    output_tokens: Optional[int] = Field(None, description="Nombre de tokens de sortie.")
    rag_parameters: Optional[RAGParameters]
    consumed_energy_Wh: Optional[float] = Field(None, description="Consommation estimée pour des modÃ¨les en local.")
    total_time: Optional[float]
class QuestionSessionMessage(BaseModel):
    session_id: str
    user_message: str
class QuestionSessionResponse(BaseModel):
    session_status: SessionStatus
    computed_message_type: str
    # TODO: utiliser une structure pour indiquer les données de consommation
    #       en tokens. Prévoir également un type générique.
    metadata: dict
    total_time: float
    message: str
    # pour faciliter le traitement cÃ´té client
    new_question: bool
    is_finished: bool
class HealthResponse(BaseModel):
    """ModÃ¨le de réponse pour le health check"""
    status: str = Field(..., description="Etat du serveur")
    rag_initialized: bool = Field(..., description="Le système RAG est-il initialisé")
    timestamp: str = Field(..., description="Horodatage du check")
    version: str = Field(..., description="Version de l'API")

class AuthRegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    email: str = Field(...)
    password: str = Field(..., min_length=6)
    role: str = Field("user")

class AuthLoginRequest(BaseModel):
    username: str = Field(...)
    password: str = Field(...)

class AuthUserResponse(BaseModel):
    user_id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: Optional[str] = None

class AuthResponse(BaseModel):
    user: AuthUserResponse
    api_key: str

qa_agent = get_qa_agent()
evaluation_agent = get_evaluator_agent("mistral-small",async_mode=True)

message_ev_agent = get_message_type_agent("ministral-3b-2410")
question_session_manager = QuestionSessionManager()
rag_session_manager = RAGSessionManager()
# donne les modèles et providers pour pouvoir initialiser les agents évaluateurs
models_evaluator = [("ministral-8b-latest", "mistral"), ("llama3.2:3b", "ollama"), ("gemma4:e2b", "ollama")]
# Contient les instances d'agent effectuant les évaluations pour chaque modÃ¨le
# dans models_evaluator
evaluators = []
final_evaluator = get_final_evaluator_agent("ministral-8b-latest")
# === GESTION DU CYCLE DE VIE ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application"""
    # Startup
    initialize_rag()
    initialize_evaluators()
    yield
    # Shutdown (si nécessaire)
    print("Arrêt du serveur : sauvegarde des sessions...")
    for session_id in question_session_manager.sessions:
        status = question_session_manager.get_session_status(session_id)
        session_dict = session_status_to_dict(status)
        session_dict["metadata"] = {
            "llm_used": "mistral-7b",
            "number_of_agents": 3,
            "server_shutdown_at": datetime.now().isoformat(),
        }
        append_session_to_json(session_dict)
    print("Sauvegarde terminée.")
    pass
# === APPLICATION FASTAPI ===
app = FastAPI(
    title="API Chatbot RAG M3C v0.1",
    description="API REST pour interroger le systÃ¨me RAG sur un corpus de documents extraits de la M3C",
    version="0.0.1",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)
app.mount("/static", StaticFiles(directory="app/static", html=True), name="static")
app.mount("/admin", StaticFiles(directory="app/static/admin", html=True), name="admin")
app.include_router(viz_router, prefix="/api/viz", tags=["viz"])
app.include_router(indexing_router)
app.include_router(embedders_router)
app.include_router(question_answer_router)
app.include_router(message_evaluator_router)
app.include_router(knowledge_items_router)
app.include_router(solr_router)

# === CONFIGURATION CORS ===
# TODO: spécifier les domaines autorisés
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production: ["http://localhost:3000", "https://votre-domaine.com"]
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, etc.
    allow_headers=["*"],  # Headers autorisés
)
# === INITIALISATION DU RAG ===
def initialize_rag():
    """
    Initialise le pipeline RAG au démarrage du serveur
    Charge:
    - L'API key OpenAI depuis .env
    - La base ChromaDB
    - L'ontologie
    - Les modÃ¨les d'embeddings et de reranking
    """
    global rag_pipeline
    print("\n" + "=" * 60)
    print("Système RAG")
    print("=" * 60 + "\n")
    # Vérifier la présence de l'API Mistral AI
    mistral_api_key = os.getenv("MISTRAL_API_KEY")
    embedder_model_name = "mistral-embed"
    try:
        # Initialiser le pipeline RAG v3 avec l'embedder
        rag_pipeline = RAGPipeline(load_local=False, embedder_name=embedder_model_name)
        # for api_visualization
        set_rag_pipeline(rag_pipeline)
        
        # Mettre à jour le nom du modèle d'embedding pour api_visualization
        set_embedding_model(embedder_model_name)
        
        return True
    except Exception as e:
        print(f"\nERREUR lors de l'initialisation du RAG: {e}\n")
        raise
def initialize_evaluators(async_mode: bool = True):
    evaluators.extend([get_evaluator_agent(model,
                                           provider=provider,
                                           async_mode=async_mode) for model, provider in models_evaluator])
# === ENDPOINTS ===
@app.get("/", tags=["Root"])
async def root():
    """Endpoint racine - Redirige vers la documentation"""
    return {
        "message": "API Chatbot RAG v0.1 - M3C",
        "documentation": "/docs",
        "health_check": "/api/health",
        "query_endpoint": "/api/query"
    }

# === ENDPOINTS D'AUTHENTIFICATION ===
@app.post("/api/auth/register", response_model=AuthResponse, tags=["Auth"])
async def register(request: AuthRegisterRequest):
    """Crée un nouveau compte utilisateur dans la table `users`."""
    try:
        user, api_key = await auth.create_user(
            username=request.username,
            email=request.email,
            password=request.password,
            role=request.role,
        )
        return AuthResponse(user=AuthUserResponse(**user), api_key=api_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR inscription: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erreur lors de la création du compte.")

@app.post("/api/auth/login", response_model=AuthResponse, tags=["Auth"])
async def login(request: AuthLoginRequest):
    """Connecte un utilisateur existant à partir de son nom d'utilisateur ou email."""
    try:
        user, api_key = await auth.authenticate_user(request.username, request.password)
        return AuthResponse(user=AuthUserResponse(**user), api_key=api_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR connexion: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erreur lors de la connexion.")

@app.get("/api/auth/me", tags=["Auth"])
async def get_current_user(authorization: Optional[str] = None):
    """Retourne l'utilisateur associé à la clé API (Bearer token) fournie."""
    user_id = auth.user_id_from_authorization(authorization)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Non authentifié.")
    user = await auth.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable.")
    return {"user": AuthUserResponse(**user)}

@app.post("/api/auth/logout", tags=["Auth"])
async def logout(authorization: Optional[str] = None):
    """Révoque la clé API courante (déconnexion)."""
    auth.revoke_token(authorization)
    return {"message": "Déconnecté."}

@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Vérifie l'état de santé du serveur et du systÃ¨me RAG
    Returns:
        HealthResponse avec le statut du serveur
    """
    return HealthResponse(
        status="healthy" if rag_pipeline is not None else "unhealthy",
        rag_initialized=rag_pipeline is not None,
        timestamp=datetime.now().isoformat(),
        version="0.1.0"
    )
#
# @app.post("/analyze_document", response_model=List[Question])
# def analyze_document(request: DocumentRequest):
#     """GénÃ¨re des questions à partir d'un document."""
#     try:
#         questions = document_analyzer(request.text)
#         return questions
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#
# @app.post("/evaluate_response", response_model=Feedback)
# def evaluate_response(request: UserResponseRequest):
#     """Ã‰value la réponse de l'utilisateur à la question en cours."""
#     try:
#         feedback = tutor_evaluator(request.response)
#         return feedback
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))
#
# @app.post("/session/{command}", response_model=Dict)
# def manage_session(command: str):
#     """GÃ¨re l'état de la session (reset, history)."""
#     try:
#         result = state_manager(command)
#         return result
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))
#
# @app.get("/current_question", response_model=Dict)
# def get_current_question():
#     """Retourne la question en cours."""
#     if not state.questions or state.current_question_index >= len(state.questions):
#         raise HTTPException(status_code=404, detail="Aucune question disponible")
#     return {
#         "question": state.questions[state.current_question_index].question,
#         "index": state.current_question_index
#     }
@app.post("/api/query/simple",
          response_model=QueryResponse,
          tags=["Query"])
async def query_simple(request: QueryRequest):
    if not request.models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun modÃ¨le sélectionné. Veuillez spécifier au moins un modÃ¨le."
        )
    try:
        print(f"\n[{datetime.now().isoformat()}] Nouvelle requête: {request.question}\n ModÃ¨le: {request.models[0]}")
        answer, total_time, consumed_energy_Wh = await rag_pipeline.query_simple(
            prompt=request.question,
            model=request.models[0]
        )
        # Construire la réponse
        response = _build_query_simple_response(request, answer, total_time, consumed_energy_Wh)
        print(f"[{datetime.now().isoformat()}] Réponse générée")
        return response
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du traitement de la requête: {str(e)}"
        )
@app.post("/api/query/rag",
          response_model=QueryResponse,
          tags=["Query"])
async def query_rag(request: QueryRequest):
    """
    Pose une question au système et retourne la réponse en fournissant les sources
    Args:
        request: QueryRequest contenant la question et les paramÃ¨tres
    Returns:
        QueryResponse avec la réponse et les sources
    Raises:
        HTTPException 503: Si le systÃ¨me RAG n'est pas initialisé
        HTTPException 500: Si une erreur se produit lors du traitement
    """
    # Vérifier que le RAG est initialisé
    if rag_pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le système RAG n'est pas encore initialisé. Veuillez réessayer dans quelques instants."
        )
    try:
        print(f"\n[{datetime.now().isoformat()}] Nouvelle requête: {request.question}")

        # On obtient ici un resource_id, on veut le document_id correspondant
        doc_id = request.rag_monodocument_id
        if request.rag_monodocument_id:
            doc_id = get_document_id_from_resource_id(await get_db_connection(), request.rag_monodocument_id)
        answer, retrieval_results, total_time, consumed_energy_Wh = await rag_pipeline.query_rag(
            prompt=request.question,
            model=request.models[0],
            k=request.k,
            reranking="bm25+" if request.use_reranking else None,
            final_prompt=None,
            sources=None,
            specified_document_id=doc_id,
        )
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du traitement de la requête: {str(e)}"
        )
    response = _build_query_rag_response(request, answer, retrieval_results, total_time, consumed_energy_Wh)
    return response

@app.post("/api/query/rag/tutorial",
          response_model=QueryResponse,
          tags=["Query"])
async def query_rag_tutorial(request: QueryRequest):
    """
    Pose une question au système et retourne l'intégralité des éléments constitutifs du RAG
    permettant de les présenter à l'utilisateur. Ils seront contenus dans l'attribut metadata
    de QueryResponse
    """
    # Vérifier que le RAG est initialisé
    if rag_pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le système RAG n'est pas encore initialisé. Veuillez réessayer dans quelques instants."
        )
    try:
        print(f"\n[{datetime.now().isoformat()}] Nouvelle requête RAG tutoriel: {request.question}")

        # On obtient ici un resource_id, on veut le document_id correspondant
        doc_id = request.rag_monodocument_id
        if request.rag_monodocument_id:
            doc_id = get_document_id_from_resource_id(await get_db_connection(), request.rag_monodocument_id)

        # On calcule normalement la réponse du RAG
        # QueryResponse
        response = await query_rag(request)

        prompt_embeddings = rag_pipeline._get_prompt_embeddings(request.question)
        best_50_chunks = await database.get_top_k_similar_chunks_qdrant(
            prompt_embeddings,
            "LD-mistral-mistral-embed-1024",
            50,
            doc_id,
            True,
            True
        )
        print(type(prompt_embeddings))
        doc_embeddings = [chunk["embedding"] for chunk in best_50_chunks]
        print("doc_embeddings", type(doc_embeddings), f"size: {len(doc_embeddings)}")
        all_embedings = [prompt_embeddings] + doc_embeddings

        umap_response = await api_visualization.compute_umap_projection(api_visualization.UMAPRequest(
            embeddings=all_embedings,
            random_state=42
        ))

        #projected_embeddings: List[List[float]] = Field(..., description="2D/3D projected coordinates")
        # le premier contient la projection des embeddings du prompt
        tutorial_metadata = {
            "prompt_projection": umap_response.projected_embeddings[0],
            "best_chunks": best_50_chunks,
            "chunk_projections": umap_response.projected_embeddings[1:],

        }
        response.metadata["tutorial_metadata"] = tutorial_metadata
        return response


    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Erreur lors du traitement"
        )


@app.post("/api/questions/recommend",
          response_model=List[Dict],
          tags=["Questions"])
async def api_recommend_questions(
    user_prompt: str,
    document_id: str,
    k: int = 5
):
    """
    Recommande les questions les plus pertinentes d'un document par rapport à un prompt utilisateur.
    
    Utilise le RAG pipeline pour calculer la pertinence en utilisant les embeddings.
    Les questions sont classées par similarité cosinus entre le prompt et le texte de la question.
    
    Args:
        user_prompt: Le texte de la requête utilisateur
        document_id: L'ID du document (document_id, pas resource_id)
        k: Nombre de questions à retourner (défaut: 5)
    
    Returns:
        Liste des questions recommandées avec leurs scores de pertinence, chaque question contient:
        - question_id: ID de la question
        - question_text: Texte de la question
        - answers: Liste des réponses
        - relevance_score: Score de pertinence (0-1)
        - chunk_id: ID du chunk associé
        - num_page: Numéro de page
    
    Raises:
        HTTPException 503: Si le système RAG n'est pas initialisé
        HTTPException 404: Si le document n'a aucune question
        HTTPException 500: Si une erreur se produit lors du traitement
    """
    # Vérifier que le RAG est initialisé
    if rag_pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le système RAG n'est pas encore initialisé. Veuillez réessayer dans quelques instants."
        )
    
    try:
        questions = await recommend_questions_for_document(
            user_prompt=user_prompt,
            document_id=document_id,
            k=k,
            rag_pipeline=rag_pipeline  # Passer l'instance globale pour éviter la duplication
        )
        
        if not questions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Aucune question trouvée pour le document {document_id}"
            )
        
        return questions
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR dans recommend_questions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recommandation de questions: {str(e)}"
        )


@app.post("/api/query/compare",
          response_model=QueryCompareResponse,
          tags=["Query"])
async def query_compare(request: QueryRequest):
    """
    Note: can be done with or without RAG
    """
    time_start = time.time()
    final_prompt, best_documents, scores = request.question, None, None
    reranking = "bm25+" if request.use_reranking else None
    if request.use_rag:
        final_prompt, best_documents = await rag_pipeline.rag_preprocess(prompt=request.question,
                                                                         reranking=reranking,
                                                                         k=request.k,
                                                                         specified_document_id=request.rag_monodocument_id,)
        print(best_documents)
    # we keep the query_simple function to get the answer
    tasks = [
        rag_pipeline.query_simple(
            prompt=final_prompt,
            model=model,
            k=request.k,
        ) for model in request.models
    ]
    answers = await asyncio.gather(*tasks)
    # rag_pipeline.query_simple gives a BaseMessage, but we want a QueryResponse.
    # so we must build it
    # request contains all the models used and
    # _build_query_simple_response takes request.models[0]
    # so we duplicate the models list to keep the list
    responses_list = []
    model_temp_list = request.models[::]
    for i, (answer, total_time, consumed_energy_Wh) in enumerate(answers):
        # and assign a list with 1 element
        request.models = [model_temp_list[i]]
        if request.use_rag:
            responses_list.append(_build_query_rag_response(request, answer, best_documents, total_time, consumed_energy_Wh))
        else:
            responses_list.append(_build_query_simple_response(request, answer, total_time, consumed_energy_Wh))
    print(f"[{datetime.now().isoformat()}] Réponses générées pour tous les modÃ¨les")
    return QueryCompareResponse(
        responses=responses_list,
        timestamp=str(datetime.now().isoformat()),
        total_time=time.time() - time_start,
        metadata={}
    )
@app.post("/api/query/single-doc-rag",
          response_model=QueryResponse,
          tags=["Query"])
async def query_single_doc_rag(request: QueryRequest):
    """
    Pose une question au systÃ¨me en utilisant le RAG sur un seul document spécifique.
    Sauvegarde également l'historique d'une session utilisateur
    Args:
        request: QueryRequest contenant la question et les paramÃ¨tres
    Returns:
        QueryResponse avec la réponse et les sources
    Raises:
        HTTPException 503: Si le systÃ¨me RAG n'est pas initialisé
        HTTPException 500: Si une erreur se produit lors du traitement
    """
    # Vérifier que le RAG est initialisé
    if rag_pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le systÃ¨me RAG n'est pas encore initialisé. Veuillez réessayer dans quelques instants."
        )
    # Vérifier qu'un document_id est fourni
    if not request.rag_monodocument_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun document_id spécifié pour le RAG sur un seul document."
        )
    # Récupérer l'historique de la session si session_id est fourni
    session_messages = []
    print("session_id:", request.session_id)
    if request.session_id:
        session = rag_session_manager.get_session(request.session_id)
        #print(session.to_messages())
        # list of {"role": "user"|"assistant", "content": "..."}
        session_messages.extend(session.to_messages())
    try:
        print(f"\n[{datetime.now().isoformat()}] Nouvelle requête single-doc RAG: {request.question}")
        # Ajouter l'historique au prompt si disponible
        prompt_with_history = request.question
        if session_messages:
            history_text = "\n\n".join([message["content"] for message in session_messages])
            #print(history_text)
            prompt_with_history = f"Historique de la session:\n{history_text}\n\nNouvelle question: {request.question}"
            print(f"{len(session_messages)} messages dans la session")
        answer, retrieval_results, total_time, consumed_energy_Wh = await rag_pipeline.query_rag(
            prompt=prompt_with_history,
            model=request.models[0],
            k=request.k,
            specified_document_id=request.rag_monodocument_id,
            reranking="bm25+" if request.use_reranking else None,
            final_prompt=None,
            sources=None
        )
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du traitement de la requête: {str(e)}"
        )
    rag_interaction = RAGInteraction(
        question=request.question,
        answer=answer.content,
        sources=retrieval_results,
        model=request.models[0],
        k=request.k,
        use_reranking=request.use_reranking,
        total_time=total_time,
        consumed_energy_Wh=consumed_energy_Wh)
    rag_session_manager.add_interaction(session_id=request.session_id,
                                        interaction=rag_interaction)
    response = _build_query_rag_response(request, answer, retrieval_results, total_time, consumed_energy_Wh)
    return response



@app.post("/api/sessions/questions/init/{document_id}",
          response_model=SessionStatus)
async def init_question_session(document_id: int,
                                premade_session: bool = True):
    """
    Initialise une nouvelle session de questions/réponses pour un document donné.
    Retourne l'ID de la session et les questions générées.
    """
    document_id = int(document_id)
    session_id = question_session_manager.create_session(document_id, premade_session)
    if not premade_session:
        # TODO: pour plus tard, en récupérant l'historique de l'utilisateur
        #       et éventuellement ses préférences. Suite de questions recommandées
        #       par LLM, IA plus classique, ou bien créée et corrigée par des utilisateurs
        #       experts ou vérifiés.
        raise NotImplementedError
    async with await get_db_connection() as conn:
        await insert_session(conn,
                                session_id,
                                None,
                                document_id,
                                datetime.now().isoformat())
    
    # on détermine les questions qui seront posées. La sélection est faite à l'avance.
    questions_ids = PREMADE_QUESTIONS_BY_DOCUMENT_ID[int(document_id)]
    async with await get_db_connection() as conn:
        questions = await get_questions_by_ids(questions_ids, conn)

        print(questions)
    # note: il y a une liste par question, car une question peut avoir plusieurs chunks
    # TODO: il faudra ajouter avec le document la méthode de chunking utilisée,
    #       car pour le même document, il peut être découpé de plusieurs maniÃ¨res, donc avoir
    #       plusieurs chunks pour la même question.
        questions_chunks = await get_chunks_by_question_ids(questions_ids, conn)
    questions_texts = [question["content"] for question in questions]
    question_pages = [chunk[0]["num_page"] for chunk in questions_chunks]

    question_session_manager.add_questions(session_id, questions_ids, questions_texts, question_pages)
    return question_session_manager.get_session_status(session_id)

@app.post("/api/sessions/questions/message",
          response_model=QuestionSessionResponse)
async def submit_question_session_message(request: QuestionSessionMessage):
    """
    Ajoute un message à la conversation d'une session. L'agent analyse la réponse pour vérifier
    si c'est la réponse à la question en cours, ou une demande de contexte supplémentaire.
    """

    # TODO: fonction trop longue, à découper

    start_time = time.time()
    total_input_tokens = 0
    total_output_tokens = 0
    session_id = request.session_id
    user_message = request.user_message
    session = question_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    if not evaluators:
        logging.error("Evaluateurs non initialisés")
        raise HTTPException(status_code=500, detail="Evaluateurs non initialisés")
    current_question_id = question_session_manager.get_current_question_id(session_id)
    if not current_question_id:
        raise HTTPException(status_code=500, detail="Erreur détectée lors du traitement de la session")
    # récupérer la question et ses réponses
    question = await get_question_by_id(await get_db_connection(),
                                        current_question_id,
                                        include_answers=True)
    # vérifier que les réponses existent
    reference_answers = [answer["content"] for answer in question["answers"]]
    # vérification du type de message.
    # -> Tuple[OutputSchema, int, int]
    result, token_count_result, output_tokens = monitor_agent_call(message_ev_agent,
                                                                   user_input=MessageTypeRequestInput(
                                                                              current_question=question["content"],
                                                                              reference_answers=reference_answers,
                                                                              user_message=user_message
                                                                   ),
                                                                   method = "run")
    message_type = result.message_type
    total_input_tokens += token_count_result
    total_output_tokens += output_tokens
    logging.info("Message type determined : {message_type}".format(message_type=message_type),)
    new_question = False
    is_finished = False
    message = ""
    user_response = UserResponse(
        question_id=current_question_id,
        question_text=question['content'],
        user_answer=user_message,
        date_sent=datetime.now(),
        evaluation=None,
        message_type=message_type
    )
    match message_type:
        case "reponse":
            if not question["answers"]:
                raise HTTPException(status_code=500, detail="Pas de réponse prévue pour cette question...")
            # Utiliser toutes les réponses disponibles pour l'évaluation
            expected_answers = [answer["content"] for answer in question["answers"]]
            evaluation_input = EvaluateRequestInput(
                question=question['content'],
                expected_answers=expected_answers,
                user_answer=user_message
            )
            # note: les evaluators sont initialisés avec des clients async.
            # pour pouvoir effectuer ces appels en parallèle.
            evaluations = []

            coroutines = [
                monitor_agent_call_async(evaluator, evaluation_input, "run_async")
                for evaluator in evaluators
            ]
            eval_results = await asyncio.gather(*coroutines)
            for result in eval_results:
                evaluation, token_count_result, output_tokens = result
                evaluations.append(evaluation)
                total_input_tokens += token_count_result
                total_output_tokens += output_tokens
            if len(evaluations) > 1:
                # /!\ contient un AgentEvaluationResult de answer_evaluation_agent.py.
                # UserResponse attend pour l'attribut evaluation un EvaluationResult de
                # question_session.py
                # Provoque souvent cette erreur, pk ?
                # Instructor does not support multiple tool calls, use List[Model] instead
                final_evaluation, token_count_result, output_tokens = monitor_agent_call(final_evaluator,
                                                            ListAgentEvaluationResult(
                                                                evaluations=evaluations),
                                                            "run")
                total_input_tokens += token_count_result
                total_output_tokens += output_tokens
            else:
                final_evaluation = evaluations[0]
            
            # Stocker les évaluations individuelles avec leurs modèles
            individual_evaluations = []
            for i, eval_result in enumerate(evaluations):
                # Le modèle de chaque évaluateur correspond à models_evaluator[i][0]
                eval_model = models_evaluator[i][0] if i < len(models_evaluator) else f"evaluator_{i}"
                individual_eval = from_AgentEvaluationResult_to_EvaluationResult(
                    eval_result, model=eval_model
                )
                individual_evaluations.append(individual_eval)
            user_response.individual_evaluations = individual_evaluations
            
            evaluation_result = from_AgentEvaluationResult_to_EvaluationResult(final_evaluation)
            user_response.evaluation = evaluation_result
            if evaluation_result.score >= 7:
                # Si le score est suffisant, passer à la question suivante
                # peut également marquer la fin de la session si c'était la dernière qst
                question_session_manager.increment_current_index(session_id)
                is_finished = question_session_manager.is_finished(session_id)
                if not is_finished:
                    new_question = True
            # le client pourra détécter les changements par rapport à l'ancienne version de
            # sessionStatus : chgt de question, question à refaire, ou fin de session
            message = evaluation_result.feedback
        case "demande_renseignement":
            # faire appel à un LLM pour répondre à la question
            message = "Message de demande de renseignement détecté (pas implémenté pour l'instant)"
            pass
        case "hors_sujet":
            message = "Message hors-sujet détecté (pas implémenté pour l'instant)"
            pass
        case "autre":
            message = "Message classé hors-catégorie..."
            pass
    total_time = time.time() - start_time
    print("user response: ", user_response)
    # mettre à jour la session
    question_session_manager.add_response(session_id, user_response)
    print("session updated:")
    print(question_session_manager.get_session(session_id))
    # Log la réponse dans le CSV pour évaluation humaine
    log_response_to_csv(session_id, user_response)
    # Sauvegarder dans la base SQL
    session_response = QuestionSessionResponse(
        session_status=question_session_manager.get_session_status(session_id),
        computed_message_type=message_type,
        message=message,
        new_question=new_question,
        is_finished=is_finished,
        total_time=total_time,
        # note: le format de token_usage se calque sur celui de LangChain
        #       le JS fonctionne sur ce format (pour l'instant)
        # TODO: il sera à modifier plus tard.
        metadata={"token_usage":{
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,}}
    )
    return session_response
@app.get("/api/sessions/rag/init/{document_id}")
async def create_rag_session(document_id: str) -> dict:
    """
    Créée un session_id de RAG retourné à l'utilisateur
    """
    session_id = rag_session_manager.create_session(document_id)
    print("session created : ", session_id)
    return {"session_id": session_id}
@app.get("/api/sessions/rag/{rag_session_id}")
async def get_rag_session(rag_session_id: str) -> RAGSession:
    """
    RécupÃ¨re l'état actuel d'une RAGSession.
    """
    print("retrieving session: ", rag_session_id)
    session = rag_session_manager.get_session(rag_session_id)
    return session
@app.get("/api/sessions/questions/export/{session_id}")
async def export_question_session(session_id: str):
    """
    Exporte les réponses d'une session au format CSV.
    """
    session = question_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    # Générer le nom du fichier CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"session_{session_id}_{timestamp}.csv"
    filepath = os.path.join("exports", filename)
    # Créer le dossier "exports" s'il n'existe pas
    os.makedirs("exports", exist_ok=True)
    # Ã‰crire le CSV
    with open(filepath, mode="w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "date_sent",
            "question_text",
            "user_answer",
            "question_id",
            "message_type",
            "score",
            "feedback",
            "model",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        prev_question = None
        for response in session["responses"]:
            row = {
                "date_sent": response.date_sent.isoformat() if hasattr(response, "date_sent") and response.date_sent else "",
                "question_text": response.question_text if hasattr(response, "question_text") else "",
                "user_answer": response.user_answer if hasattr(response, "user_answer") else "",
                "question_id": response.question_id if hasattr(response, "question_id") else "",
                "message_type": response.message_type if hasattr(response, "message_type") else "",
                "score": response.evaluation.score if hasattr(response, "evaluation") and response.evaluation and hasattr(response.evaluation, "score") else "",
                "feedback": response.evaluation.feedback if hasattr(response, "evaluation") and response.evaluation and hasattr(response.evaluation, "feedback") else "",
                "model": response.evaluation.model if hasattr(response, "evaluation") and response.evaluation and hasattr(response.evaluation, "model") else "",
            }
            if row["question_text"] == prev_question:
                row["question_text"] = ""
            else:
                prev_question = row["question_text"]
            writer.writerow(row)
    return FileResponse(filepath, media_type="text/csv", filename=filename)

@app.get("/api/sessions/questions/{session_id}", tags=["Sessions"])
async def get_question_session(session_id: str):
    """
    Récupère une session de questions/réponses par son ID.
    
    Args:
        session_id: Identifiant de la session
    
    Returns:
        SessionStatus: L'état complet de la session avec toutes les réponses
    """
    try:
        session = question_session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session non trouvée")
        return session
    except Exception as e:
        print(f"Erreur lors de la récupération de la session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur: {str(e)}"
        )

@app.get("/api/sessions/rag/export/{session_id}")
async def export_rag_session(session_id: str):
    # writes the csv
    file_path = "rag_sessions_csv/{session_id}.csv".format(session_id=session_id)
    print("creating file at", file_path)
    success = rag_session_manager.export_session_to_csv(session_id)
    if not success:
        raise HTTPException(status_code=500, detail="Erreur lors de la création du fichier CSV. Veuillez réessayer plus tard.")
    return FileResponse(file_path, media_type="text/csv", filename=file_path)

@app.get("/get_pdf/by_filename")
async def get_pdf_by_filename(file_name: str):
    """
    Effectue une requête sur le vrai site de la M3C à partir du file_name,
    contenant l'extension
    """
    return await _get_pdf_by_filename(file_name)

@app.get("/get_pdf/by_id")
async def get_pdf_by_id(resource_id: int):
    """
    Requête la base MySQL avec le resource_id (table resource) présent dans text_chunks pour obtenir
    le nom du PDF et le retourner
    """
    print("get_pdf_by_id")
    async with await get_db_connection() as conn:
        pdf_name = await get_pdf_name_from_resource_id(conn, resource_id)
    if not pdf_name:
        raise HTTPException(status_code=404, detail="Aucun PDF trouvé pour le resource_id {}".format(resource_id))
    return await _get_pdf_by_filename(pdf_name)

async def _get_pdf_by_filename(filename: str):
    """
    Helper qui requête le PDF sur le site officiel de la M3C.
    Retourne l'objet Response qui envoie le PDF
    """
    url = M3C_BASE_URL+filename
    try:
        print("_get_pdf_by_filename")
        pdf_bytes = await download_pdf(url)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"'
            }
        )
    except Exception as e:
        print(f"Erreur lors du téléchargement de {filename}: {str(e)}")
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur - le PDF n'a pas pu être récupéré:")

@app.get("/api/documents", response_model=DocumentsListResponse, tags=["Documents"])
async def get_documents_list():
    """
    RécupÃ¨re la liste de tous les documents disponibles dans la base de données.
    Returns:
        DocumentsListResponse: Liste des documents avec leurs métadonnées
    """
    try:
        # Connexion à la base de données
        async with await get_db_connection() as conn:
            documents = await get_all_documents(conn)

        # Construire la réponse
        document_responses = []
        print("retrieved!")
        for doc in documents:
            document_responses.append(DocumentResponse(
                document_id=doc["document_id"],
                source_id=doc["resource_id"],
                file_name=doc["file_name"],
                title=doc["title"],
                author=doc["creator"],
                created_at=str(doc["created_at"]),
                updated_at=str(doc["updated_at"])
            ))
        return DocumentsListResponse(
            documents=document_responses,
            count=len(document_responses),
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR lors de la récupération des documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des documents: {str(e)}"
        )


# Modèle pour la génération de questions à partir d'un texte
class QASingleRequest(BaseModel):
    """Modèle de requête pour générer des questions à partir d'un texte"""
    message: Optional[str] = Field(None, description="Message ou instruction optionnel")
    document: str = Field(..., description="Texte du document/chunk sur lequel générer des questions", min_length=10)
    num_questions: int = Field(3, description="Nombre de questions à générer", ge=1, le=10)
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


@app.post("/api/qa-single", response_model=QASingleResponse, tags=["Query"])
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
        model_name = request.model or "mistral-small"
        
        # Définir provider et model
        provider_model = model_name.split("/") if "/" in model_name else ["mistral", model_name]
        provider = provider_model[0] if len(provider_model) > 0 else "mistral"
        model = provider_model[1] if len(provider_model) > 1 else model_name

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

@app.get("/api/questions/{document_id}", response_model=QuestionsListResponse, tags=["Questions"])
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

# === ENDPOINTS D'ÉVALUATION ===
@app.post("/api/evaluate", tags=["Evaluation"])
async def evaluate_answer(request: EvaluateRequestInput):
    """
    Évalue une réponse utilisateur par rapport à des réponses attendues.
    Utilise l'agent évaluateur avec le modèle spécifié ou par défaut.
    
    Args:
        request: EvaluateRequestInput avec question, expected_answers, user_answer, model
        model est au format <provider>/<model_name>
    
    Returns:
        AgentEvaluationResult avec score (1-10) et feedback
    """
    try:
        print(f"[{datetime.now().isoformat()}] Évaluation de réponse demandée avec modèle: {request.model}")
        
        # Utiliser le modèle spécifié ou le modèle par défaut
        provider, model = tuple(request.model.split("/")) if request.model else ("mistral", "mistral-small")
        # Créer un agent avec le modèle spécifié
        evaluator = get_evaluator_agent(model, provider=provider, async_mode=True)
        evaluation = await evaluator.run_async(request)
        print(f"[{datetime.now().isoformat()}] Évaluation terminée: score={evaluation.score}")
        return evaluation
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR lors de l'évaluation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'évaluation: {str(e)}"
        )

@app.get("/api/reference-answers", tags=["Evaluation"])
async def get_all_reference_answers():
    """
    Récupère toutes les paires question/réponse de référence depuis le CSV.
    
    Returns:
        Dictionnaire avec question_id comme clé et {answer_id, question_content, response_answer} comme valeur
    """
    try:
        reference_data = get_reference_answers()
        return {"reference_answers": reference_data, "count": len(reference_data)}
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR lors du chargement des réponses de référence: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement des réponses de référence: {str(e)}"
        )

@app.get("/api/reference-answers/{question_id}", tags=["Evaluation"])
async def get_reference_answer_by_id(question_id: int):
    """
    Récupère la réponse de référence pour une question spécifique.
    
    Args:
        question_id: ID de la question
    
    Returns:
        Dictionnaire avec answer_id, question_content, response_answer
    """
    try:
        reference_answer = get_reference_answer(question_id)
        if reference_answer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Aucune réponse de référence trouvée pour la question {question_id}"
            )
        return reference_answer
    except HTTPException:
        raise
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur: {str(e)}"
        )

class EvaluationSaveRequest(BaseModel):
    """Modèle de requête pour sauvegarder une évaluation"""
    question_id: int = Field(..., description="ID de la question")
    answer_id: Optional[str] = Field(None, description="ID de la réponse de référence")
    evaluated_answer: str = Field(..., description="Réponse qui a été évaluée")
    score: Optional[int] = Field(None, description="Note (1-10)", ge=1, le=10)
    feedback: str = Field(..., description="Commentaire sur l'évaluation")
    evaluation_type: str = Field("auto", description="Type d'évaluation: 'auto' ou 'manual'")
    evaluation_source: Optional[str] = Field(None, description="Source de la réponse évaluée: 'llm' ou 'user'")
    model_used: Optional[str] = Field(None, description="Modèle utilisé pour l'évaluation automatique")
    question_content: Optional[str] = Field(None, description="Contenu de la question")
    reference_answer: Optional[str] = Field(None, description="Réponse de référence")


class EvaluationFeedbackRequest(BaseModel):
    """Modèle de requête pour sauvegarder un feedback humain sur une évaluation IA"""
    question_id: int = Field(..., description="ID de la question")
    chunk_id: Optional[str] = Field(None, description="ID du chunk associé")
    question_content: Optional[str] = Field(None, description="Contenu de la question")
    user_answer: str = Field(..., description="Réponse qui a été évaluée")
    ai_score: int = Field(..., description="Note générée par l'IA", ge=1, le=10)
    ai_feedback: str = Field(..., description="Commentaire généré par l'IA")
    human_rating: int = Field(..., description="Note humaine sur l'évaluation IA (1-10)", ge=1, le=10)
    human_comment: Optional[str] = Field(None, description="Commentaire humain sur l'évaluation IA")


@app.post("/api/evaluations/save", tags=["Evaluation"])
async def save_evaluation(request: EvaluationSaveRequest):
    """
    Sauvegarde une évaluation dans le fichier question-answer-reference-eval.csv.
    
    Args:
        request: EvaluationSaveRequest avec toutes les données d'évaluation
    
    Returns:
        Message de confirmation avec le chemin du fichier
    """
    try:
        evaluation_data = request.model_dump()
        filepath = log_evaluation_to_csv(evaluation_data)
        print(f"[{datetime.now().isoformat()}] Évaluation sauvegardée dans {filepath}")
        return {
            "message": "Évaluation sauvegardée avec succès",
            "filepath": filepath,
            "evaluation_id": f"{request.question_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR lors de la sauvegarde: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la sauvegarde: {str(e)}"
        )


@app.post("/api/evaluation-feedback/save", tags=["Evaluation"])
async def save_evaluation_feedback(request: EvaluationFeedbackRequest):
    """
    Sauvegarde un feedback humain sur une évaluation IA dans le fichier evaluation-feedback.csv.
    
    Args:
        request: EvaluationFeedbackRequest avec toutes les données de feedback
    
    Returns:
        Message de confirmation avec le chemin du fichier
    """
    print(request)
    try:
        feedback_data = request.model_dump()
        filepath = log_feedback_to_csv(feedback_data)
        print(f"[{datetime.now().isoformat()}] Feedback sur évaluation IA sauvegardé dans {filepath}")
        return {
            "message": "Feedback sur évaluation IA sauvegardé avec succès",
            "filepath": filepath,
            "feedback_id": f"{request.question_id}_fb_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERREUR lors de la sauvegarde du feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la sauvegarde du feedback: {str(e)}"
        )


async def _rag_preprocess(request: QueryRequest)-> tuple[str, List[RAGSource]]:
    print("_rag_preprocess")
    final_prompt, best_documents = request.question, None, None
    if request.use_rag:
        final_prompt, best_documents = await rag_pipeline.rag_preprocess(request.question,
                                                                request.use_reranking,
                                                                         request.k)
    return final_prompt, best_documents
def _build_query_simple_response(request: QueryRequest,
                                 answer: BaseMessage,
                                 total_time: float,
                                 consumed_energy_Wh: float) -> QueryResponse:
    response = QueryResponse(
        answer=answer.content,
        total_time=total_time,
        metadata={
            "model": request.models[0],
            "k": request.k,
            "token_usage": answer.usage_metadata,
            "consumed_energy_Wh": consumed_energy_Wh
        },
        timestamp=datetime.now().isoformat()
    )
    print(f"[{datetime.now().isoformat()}] Réponse générée")
    return response
def _build_query_rag_response(request: QueryRequest,
                              answer: BaseMessage,
                              retrieval_results: list[RAGSource],
                              total_time: float,
                              consumed_energy_Wh: float) -> QueryResponse:
    # useful data :
    # response_metadata={
    # 'token_usage': {'prompt_tokens': 944,
    #                 'total_tokens': 1630,
    #                 'completion_tokens': 686},
    # 'model_name': 'mistral-large-2411',
    # 'model': 'mistral-large-2411',
    # 'finish_reason': 'stop'}
    # id='run--9ec94e4e-1bd4-4702-b3e5-ca4d42eaae33-0'
    # usage_metadata={'input_tokens': 944,
    #                 'output_tokens': 686,
    #                 'total_tokens': 1630}
    # Convertir les résultats en format API
    print("_build_query_rag_response")
    # Construire la réponse
    response = QueryResponse(
        answer=answer.content,
        total_time=total_time,
        sources=retrieval_results,
        metadata={
            "model": request.models[0],
            "k": request.k,
            "use_reranking": request.use_reranking,
            "include_quantitative": request.include_quantitative,
            "num_sources": len(retrieval_results),
            "token_usage": answer.usage_metadata,
            "consumed_energy_Wh": consumed_energy_Wh
        },
        timestamp=datetime.now().isoformat()
    )
    print(f"[{datetime.now().isoformat()}] Réponse générée avec {len(response.sources)} sources")
    return response

def split_text_into_chunks(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Découpe un texte en chunks avec recouvrement.
    
    Args:
        text: Texte à découper
        chunk_size: Taille maximale d'un chunk en caractères
        overlap: Nombre de caractères de recouvrement entre les chunks
        
    Returns:
        Liste des chunks
    """
    if not text or chunk_size <= 0:
        return []
    
    chunks = []
    start = 0
    overlap = min(overlap, chunk_size)  # Assurer que overlap <= chunk_size
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    
    return chunks


# ============================================================================
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
# ENDPOINTS D'ADMINISTRATION
# ============================================================================

@app.get("/api/admin/documents", tags=["Admin"])
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


@app.get("/api/admin/stats", tags=["Admin"])
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




def append_session_to_json(session_dict: Dict[str, Any], file_path: str = "sessions_backup.json"):
    """
    Ajoute une session à un fichier JSON existant.
    Crée le fichier s'il n'existe pas.
    """
    file = Path(file_path)
    sessions_data = []
    # Lire le contenu existant si le fichier existe
    if file.exists():
        with open(file, "r", encoding="utf-8") as f:
            try:
                sessions_data = json.load(f)
            except json.JSONDecodeError:
                sessions_data = []
    # Ajouter la nouvelle session
    sessions_data.append(session_dict)
    # Réécrire le fichier
    with open(file, "w", encoding="utf-8") as f:
        json.dump(sessions_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    # Configuration du serveur
    host = os.getenv("API_HOST", "0.0.0.0")  # 0.0.0.0 pour accepter les connexions externes
    port = int(os.getenv("API_PORT", "8000"))
    reload = False
    print("\n" + "=" * 60)
    print("DÃ‰MARRAGE DU SERVEUR API")
    print("=" * 60)
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Reload: {reload}")
    print(f"Documentation: http://localhost:{port}/docs")
    print("=" * 60 + "\n")
    print("Setting the asyncio event_loop_policy to asyncio.WindowsSelectorEventLoopPolicy")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print("Event loop policy:", asyncio.get_event_loop_policy())
    print("Event loop type:", type(asyncio.get_event_loop()))
    print("cwd =", os.getcwd())
    print("exists =", os.path.exists("rag_sessions_csv"))
    print("absolute =", os.path.abspath("rag_sessions_csv"))
    print("=" * 60 + "\n")
    print(torch.cuda.is_available())
    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        loop="asyncio"
    )
