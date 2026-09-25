import asyncio
import logging
import os
import time
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, ConfigDict
from dotenv import load_dotenv

import database
import auth
from indexing.services import download_pdf
from rag_pipeline import RAGPipeline, RAGSource
from dependencies import RagPipelineDep
from agents.answer_evaluator_agent import get_evaluator_agent
from agents.instructor_factory import MISTRAL_MODELS, GOOGLE_MODELS
from agents.message_evaluator_agent import get_message_type_agent
from database.database import (get_db_connection,
                               get_document_id_from_resource_id,
                               M3C_BASE_URL, get_pdf_name_from_resource_id)
from agents.token_monitor import *
import asyncio
from rag_session import RAGInteraction
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
from question_answer.generation_services import recommend_questions_for_document

# Import du router Solr
from solr.router import router as solr_router

# Import du router de consultation des documents et de leurs chunks
from documents.router import router as documents_router

# Import du router d'authentification
from routers.auth import router as auth_router
from routers.observations import router as observations_router
from routers.observations_admin import router as observations_admin_router
from routers.sessions import router as sessions_router
from routers.evaluations import router as evaluations_router
from routers.models import router as models_router

# Import du router de profil utilisateur
from profile.router import router as profile_router

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
class HealthResponse(BaseModel):
    """ModÃ¨le de réponse pour le health check"""
    status: str = Field(..., description="Etat du serveur")
    rag_initialized: bool = Field(..., description="Le système RAG est-il initialisé")
    timestamp: str = Field(..., description="Horodatage du check")
    version: str = Field(..., description="Version de l'API")



# donne les modèles et providers pour pouvoir initialiser les agents évaluateurs
models_evaluator = [("ministral-8b-latest", "mistral"),
                    ("ministral-14b-2512", "mistral"),
                    ("ministral-3b-latest", "mistral")]
# Contient les instances d'agent effectuant les évaluations pour chaque modèle
# dans models_evaluator

# === GESTION DU CYCLE DE VIE ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application"""
    # Startup
    initialize_rag(app)
    initialize_evaluators(app)
    app.state.message_ev_agent = get_message_type_agent("ministral-3b-2410")
    yield
    # Shutdown (si nécessaire)
    print("Arrêt du serveur : sauvegarde des sessions...")
    sessions_router.persist_sessions_on_shutdown(app)
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
app.include_router(documents_router)
app.include_router(profile_router)
app.include_router(auth_router)
app.include_router(observations_router)
app.include_router(observations_admin_router)
app.include_router(sessions_router)
app.include_router(evaluations_router)
app.include_router(question_answer_router)
app.include_router(models_router)

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
def initialize_rag(app: FastAPI):
    """
    Initialise le pipeline RAG au démarrage du serveur
    Charge:
    - L'API key OpenAI depuis .env
    - La base ChromaDB
    - L'ontologie
    - Les modÃ¨les d'embeddings et de reranking
    """
    print("\n" + "=" * 60)
    print("Système RAG")
    print("=" * 60 + "\n")

    embedder_model_name = "mistral-embed"
    try:
        pipeline = RAGPipeline(load_local=False, embedder_name=embedder_model_name)
        app.state.rag_pipeline = pipeline
        # for api_visualization
        set_rag_pipeline(pipeline)
        
        # Mettre à jour le nom du modèle d'embedding pour api_visualization
        set_embedding_model(embedder_model_name)
        
        return True
    except Exception as e:
        print(f"\nERREUR lors de l'initialisation du RAG: {e}\n")
        raise

def initialize_evaluators(app: FastAPI, async_mode: bool = True):
    app.state.evaluators = [get_evaluator_agent(model,
                                           provider=provider,
                                                async_mode=async_mode) for model, provider in models_evaluator]
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

@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Vérifie l'état de santé du serveur et du systÃ¨me RAG
    Returns:
        HealthResponse avec le statut du serveur
    """
    return HealthResponse(
        status="healthy" if getattr(app.state, "rag_pipeline", None) is not None else "unhealthy",
        rag_initialized=getattr(app.state, "rag_pipeline", None) is not None,
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
async def query_simple(request: QueryRequest, rag_pipeline: RagPipelineDep):
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
async def query_rag(request: QueryRequest, rag_pipeline: RagPipelineDep):
    """
    Pose une question au système et retourne la réponse en fournissant les sources
    Args:
        request: QueryRequest contenant la question et les paramètres
    Returns:
        QueryResponse avec la réponse et les sources
    Raises:
        HTTPException 503: Si le système RAG n'est pas initialisé
        HTTPException 500: Si une erreur se produit lors du traitement
    """
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
async def query_rag_tutorial(request: QueryRequest, rag_pipeline: RagPipelineDep):
    """
    Pose une question au système et retourne l'intégralité des éléments constitutifs du RAG
    permettant de les présenter à l'utilisateur. Ils seront contenus dans l'attribut metadata
    de QueryResponse
    """
    try:
        print(f"\n[{datetime.now().isoformat()}] Nouvelle requête RAG tutoriel: {request.question}")

        # On obtient ici un resource_id, on veut le document_id correspondant
        doc_id = request.rag_monodocument_id
        if request.rag_monodocument_id:
            doc_id = get_document_id_from_resource_id(await get_db_connection(), request.rag_monodocument_id)

        # On calcule normalement la réponse du RAG
        # QueryResponse
        response = await query_rag(request, rag_pipeline)

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
    k: int = 5,
    rag_pipeline: RagPipelineDep = None,
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
async def query_compare(request: QueryRequest, rag_pipeline: RagPipelineDep):
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
async def query_single_doc_rag(request: QueryRequest, rag_pipeline: RagPipelineDep):
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
        session = sessions_router.rag_session_manager.get_session(request.session_id)
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
    sessions_router.rag_session_manager.add_interaction(session_id=request.session_id,
                                                        interaction=rag_interaction)
    response = _build_query_rag_response(request, answer, retrieval_results, total_time, consumed_energy_Wh)
    return response



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
# ============================================================================

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
