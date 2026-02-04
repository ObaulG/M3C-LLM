import asyncio
import copy
import csv
import os
import time
import uuid
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from langchain_core.messages import BaseMessage

from pydantic import BaseModel, Field, ConfigDict

from dotenv import load_dotenv
from starlette.responses import JSONResponse

from rag_pipeline import RAGPipeline, RetrievalResult, RAGSource
from question_session import SessionManager, SessionResponse, EvaluateRequest, UserResponse
from helper import calculate_cosine_similarity
from agents.qa_agent import get_qa_agent
from agents.answer_evaluator_agent import get_evaluator_agent

import asyncio
if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


import uvicorn

# Charger les variables d'environnement
load_dotenv()


# === MODELS PYDANTIC ===


class QueryRequest(BaseModel):
    """Modèle de requête pour poser une question"""
    question: str = Field(..., description="Question à poser au chatbot", min_length=1)
    models: List[str] = Field(..., description="Modèles utilisés pour la génération")
    k: int = Field(3, description="Nombre de documents à récupérer", ge=1, le=20)
    use_rag: bool = Field(False, description="Utiliser le RAG pour s'appuyer sur des ressources existantes")
    use_reranking: bool = Field(False, description="Utiliser le reranking pour améliorer les résultats")
    include_quantitative: bool = Field(True, description="Inclure les données quantitatives")

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
    """Modèle de réponse à une question"""
    answer: str = Field(..., description="Réponse générée par le chatbot")
    sources: Optional[List[RAGSource]] = Field(
        None,
        description="Sources utilisées pour la réponse dans le cas où le RAG est activé"
    )
    total_time: float = Field(..., description="Temps total de la génération")
    metadata: Dict = Field(..., description="Métadonnées de la requête")
    timestamp: str = Field(..., description="Horodatage de la réponse")

class QueryCompareResponse(BaseModel):
    responses: List[QueryResponse]
    total_time: float = Field(..., description="Temps total de la génération")
    metadata: Dict = Field(..., description="Métadonnées de la requête")
    timestamp: str = Field(..., description="Horodatage de la réponse")


class HealthResponse(BaseModel):
    """Modèle de réponse pour le health check"""
    status: str = Field(..., description="État du serveur")
    rag_initialized: bool = Field(..., description="Le système RAG est-il initialisé")
    timestamp: str = Field(..., description="Horodatage du check")
    version: str = Field(..., description="Version de l'API")

qa_agent = get_qa_agent()
evaluation_agent = get_evaluator_agent()
session_manager = SessionManager()

# === GESTION DU CYCLE DE VIE ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application"""
    # Startup
    initialize_rag()
    yield
    # Shutdown (si nécessaire)
    pass


# === APPLICATION FASTAPI ===



app = FastAPI(
    title="API Chatbot RAG M3C v0.1",
    description="API REST pour interroger le système RAG sur un corpus de documents extraits de la M3C",
    version="0.0.1",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# === CONFIGURATION CORS ===

# Pour les tests en local, on autorise toutes les origines
# En production, spécifier les domaines autorisés
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
    - Les modèles d'embeddings et de reranking
    """
    global rag_pipeline

    print("\n" + "=" * 60)
    print("INITIALISATION DU SYSTÈME RAG v3")
    print("=" * 60 + "\n")

    # Vérifier la présence de l'API Mistral AI
    mistral_api_key = os.getenv("MISTRAL_API_KEY")
    if not mistral_api_key:
        raise RuntimeError(
            "MISTRAL_API_KEY non trouvée dans les variables d'environnement. "
            "Veuillez créer un fichier .env avec votre clé API."
        )

    try:
        # Initialiser le pipeline RAG v3
        rag_pipeline = RAGPipeline()
        print("\n" + "=" * 60)
        print("Système RAG simple initialisé")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"\nERREUR lors de l'initialisation du RAG: {e}\n")
        raise


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
    Vérifie l'état de santé du serveur et du système RAG

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
#     """Génère des questions à partir d'un document."""
#     try:
#         questions = document_analyzer(request.text)
#         return questions
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#
# @app.post("/evaluate_response", response_model=Feedback)
# def evaluate_response(request: UserResponseRequest):
#     """Évalue la réponse de l'utilisateur à la question en cours."""
#     try:
#         feedback = tutor_evaluator(request.response)
#         return feedback
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))
#
# @app.post("/session/{command}", response_model=Dict)
# def manage_session(command: str):
#     """Gère l'état de la session (reset, history)."""
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
    try:
        print(f"\n[{datetime.now().isoformat()}] Nouvelle requête: {request.question}\n Modèle: {request.models[0]}")

        answer, total_time = await rag_pipeline.query_simple(
            prompt=request.question,
            model=request.models[0]
        )

        # Construire la réponse
        response = _build_query_simple_response(request, answer, total_time)
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
        request: QueryRequest contenant la question et les paramètres

    Returns:
        QueryResponse avec la réponse et les sources

    Raises:
        HTTPException 503: Si le système RAG n'est pas initialisé
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
        answer, retrieval_results, total_time = await rag_pipeline.query_rag(
            prompt=request.question,
            model=request.models[0],
            k=request.k,
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
    response = _build_query_rag_response(request, answer, retrieval_results, total_time)

    return response


@app.post("/api/query/compare",
          response_model=QueryCompareResponse,
          tags=["Query"])
async def query_compare(request: QueryRequest):
    """
    Note: can be done with or without RAG
    """
    time_start = time.time()
    print("Event loop policy:", asyncio.get_event_loop_policy())
    print("Event loop type:", type(asyncio.get_event_loop()))
    final_prompt, best_documents, scores = request.question, None, None
    if request.use_rag:
        final_prompt, best_documents = await rag_pipeline.rag_preprocess(request.question,
                                                                request.use_reranking,
                                                                           request.k)
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
    for i, (answer, total_time) in enumerate(answers):
        # and assign a list with 1 element
        request.models = [model_temp_list[i]]

        if request.use_rag:
            responses_list.append(_build_query_rag_response(request, answer, best_documents, total_time))
        else:
            responses_list.append(_build_query_simple_response(request, answer, total_time))
    print(f"[{datetime.now().isoformat()}] Réponses générées pour tous les modèles")
    return QueryCompareResponse(
        responses=responses_list,
        timestamp=str(datetime.now().isoformat()),
        total_time=time.time() - time_start,
        metadata={}
    )

@app.post("/api/sessions/init/{document_id}")
async def init_session(document_id: str):
    """
    Initialise une nouvelle session pour un document donné.
    Retourne l'ID de la session et les questions générées.
    """
    # Générer les questions/réponses pour le document
    response = qa_agent.run({"message": "Génère 3 questions.", "document": document_id})

    # Créer une nouvelle session
    session_id = str(uuid.uuid4())
    session_manager.create_session(session_id, document_id)
    session_manager.add_questions(session_id, response.questions_answers)

    return {
        "session_id": session_id,
        "document_id": document_id,
        "questions": response.questions_answers,
    }

@app.post("/api/sessions/{session_id}/answer")
async def submit_answer(
    session_id: str,
    question_index: int,
    user_answer: str,
):
    """
    Soumet une réponse utilisateur pour une question donnée.
    Retourne l'évaluation de la réponse.
    """
    # Récupérer la session
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")

    # Récupérer la question correspondante
    if question_index >= len(session["questions"]):
        raise HTTPException(status_code=400, detail="Index de question invalide")

    question = session["questions"][question_index]
    expected_answer = question.answer_text

    # Évaluer la réponse
    evaluation_input = EvaluateRequest(
        question=question.question_text,
        expected_answer=expected_answer,
        user_answer=user_answer,
    )
    evaluation = evaluation_agent.run(evaluation_input)

    # Calculer la similarité cosinus
    cosine_sim = calculate_cosine_similarity(question.question_text, user_answer)

    # Stocker la réponse
    user_response = UserResponse(
        question=question.question_text,
        expected_answer=expected_answer,
        user_answer=user_answer,
        score=evaluation.score,
        feedback=evaluation.feedback,
        cosine_similarity=cosine_sim,
        timestamp=datetime.now().isoformat(),
    )
    session_manager.add_response(session_id, user_response)

    return {
        "score": evaluation.score,
        "feedback": evaluation.feedback,
        "cosine_similarity": cosine_sim,
    }

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """
    Récupère l'état actuel d'une session.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")

    return SessionResponse(
        session_id=session_id,
        document_id=session["document_id"],
        responses=session["responses"],
        completed=session["completed"],
    )

@app.get("/api/sessions/{session_id}/export")
async def export_session(session_id: str):
    """
    Exporte les réponses d'une session au format CSV.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")

    # Générer le nom du fichier CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"session_{session_id}_{timestamp}.csv"
    filepath = os.path.join("exports", filename)

    # Créer le dossier "exports" s'il n'existe pas
    os.makedirs("exports", exist_ok=True)

    # Écrire le CSV
    with open(filepath, mode="w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "timestamp",
            "question",
            "expected_answer",
            "user_answer",
            "score",
            "feedback",
            "cosine_similarity",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for response in session["responses"]:
            writer.writerow(response.dict())

    return JSONResponse(
        content={"message": "Export réussi", "filename": filename},
        headers={"Location": f"/static/exports/{filename}"},
    )

@app.get("/get_pdf")
async def get_pdf(source_file: str):
    file_path = f"documents/test-m3c/{source_file}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    return FileResponse(file_path, media_type="application/pdf")


async def _rag_preprocess(request: QueryRequest)-> tuple[str, List[RAGSource]]:
    print("_rag_preprocess")
    print("Event loop policy:", asyncio.get_event_loop_policy())
    print("Event loop type:", type(asyncio.get_event_loop()))
    final_prompt, best_documents = request.question, None, None
    if request.use_rag:
        final_prompt, best_documents = await rag_pipeline.rag_preprocess(request.question,
                                                                   request.use_reranking,
                                                                         request.k)
    return final_prompt, best_documents

def _build_query_simple_response(request: QueryRequest,
                                 answer: BaseMessage,
                                 total_time: float) -> QueryResponse:
    response = QueryResponse(
        answer=answer.content,
        total_time=total_time,
        metadata={
            "model": request.models[0],
            "k": request.k,
            "token_usage": answer.usage_metadata
        },
        timestamp=datetime.now().isoformat()
    )

    print(f"[{datetime.now().isoformat()}] Réponse générée")

    return response


def _build_query_rag_response(request: QueryRequest,
                              answer: BaseMessage,
                              retrieval_results: list[RAGSource],
                              total_time: float,):
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
            "token_usage": answer.usage_metadata
        },
        timestamp=datetime.now().isoformat()
    )

    print(f"[{datetime.now().isoformat()}] Réponse générée avec {len(response.sources)} sources")

    return response


if __name__ == "__main__":
    # Configuration du serveur
    host = os.getenv("API_HOST", "0.0.0.0")  # 0.0.0.0 pour accepter les connexions externes
    port = int(os.getenv("API_PORT", "8000"))
    reload = True

    print("\n" + "=" * 60)
    print("DÉMARRAGE DU SERVEUR API")
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
    print("=" * 60 + "\n")

    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        loop="asyncio"
    )
