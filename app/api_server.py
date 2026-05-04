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

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from langchain_core.messages import BaseMessage

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Tuple
from datetime import datetime

from dotenv import load_dotenv
from starlette.responses import JSONResponse

from rag_pipeline import RAGPipeline, RetrievalResult, RAGSource
from question_session import (PREMADE_QUESTIONS_BY_DOCUMENT_ID,
                              SessionManager,
                              EvaluateRequest,
                              UserResponse,
                              SessionStatus,
                              EvaluationResult,
                              from_AgentEvaluationResult_to_EvaluationResult, session_status_to_dict)

from agents.qa_agent import get_qa_agent
from agents.answer_evaluator_agent import get_evaluator_agent, EvaluateRequestInput, get_final_evaluator_agent, \
    ListAgentEvaluationResult
from agents.message_evaluator_agent import get_message_type_agent, MessageTypeRequestInput
from database.database import (get_db_connection,
                               get_all_documents,
                               get_question_by_id,
                               get_questions_by_ids,
                               get_chunks_by_question_id,
                               get_chunks_by_question_ids)

from agents.token_monitor import *

import asyncio
if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import torch

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

class DocumentResponse(BaseModel):
    """Modèle de réponse pour un document"""
    document_id: str = Field(..., description="Identifiant du document")
    file_name: str = Field(..., description="Nom du fichier")
    file_path: str = Field(..., description="Chemin du fichier")
    file_size: int = Field(..., description="Taille du fichier en octets")
    created_at: str = Field(..., description="Date de création")
    updated_at: str = Field(..., description="Date de mise à jour")

class DocumentsListResponse(BaseModel):
    """Modèle de réponse pour la liste des documents"""
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
    consumed_energy_Wh: Optional[float] = Field(None, description="Consommation estimée pour des modèles en local.")
    total_time: Optional[float]

class SessionMessage(BaseModel):
    session_id: str
    user_message: str

class SessionResponse(BaseModel):
    session_status: SessionStatus
    computed_message_type: str
    # TODO: utiliser une structure pour indiquer les données de consommation
    #       en tokens. Prévoir également un type générique.
    metadata: dict
    total_time: float
    message: str

    # pour faciliter le traitement côté client
    new_question: bool
    is_finished: bool

class HealthResponse(BaseModel):
    """Modèle de réponse pour le health check"""
    status: str = Field(..., description="État du serveur")
    rag_initialized: bool = Field(..., description="Le système RAG est-il initialisé")
    timestamp: str = Field(..., description="Horodatage du check")
    version: str = Field(..., description="Version de l'API")

qa_agent = get_qa_agent()
evaluation_agent = get_evaluator_agent("mistral-small")
final_evaluator = get_final_evaluator_agent("mistral-small")
message_ev_agent = get_message_type_agent()
session_manager = SessionManager()
models_evaluator = ["ministral-8b-latest"]

# Contient les instances d'agent effectuant les évaluations pour chaque modèle
# dans models_evaluator
evaluators = []
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
    for session_id in session_manager.sessions:
        status = session_manager.get_session_status(session_id)
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
        rag_pipeline = RAGPipeline(load_local=False)
        print("\n" + "=" * 60)
        print("Système RAG simple initialisé")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"\nERREUR lors de l'initialisation du RAG: {e}\n")
        raise

def initialize_evaluators(async_mode: bool = True):
    evaluators.extend([get_evaluator_agent(model,
                                           provider="mistral",
                                           async_mode=async_mode) for model in models_evaluator])

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

    if not request.models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun modèle sélectionné. Veuillez spécifier au moins un modèle."
        )

    try:
        print(f"\n[{datetime.now().isoformat()}] Nouvelle requête: {request.question}\n Modèle: {request.models[0]}")

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
        answer, retrieval_results, total_time, consumed_energy_Wh = await rag_pipeline.query_rag(
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
    response = _build_query_rag_response(request, answer, retrieval_results, total_time, consumed_energy_Wh)

    return response


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
                                                                         k=request.k)
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
    print(f"[{datetime.now().isoformat()}] Réponses générées pour tous les modèles")
    return QueryCompareResponse(
        responses=responses_list,
        timestamp=str(datetime.now().isoformat()),
        total_time=time.time() - time_start,
        metadata={}
    )

@app.post("/api/sessions/init/{document_id}",
          response_model=SessionStatus)
async def init_session(document_id: str,
                       premade_session: bool = True):
    """
    Initialise une nouvelle session pour un document donné.
    Retourne l'ID de la session et les questions générées.
    """

    session_id = session_manager.create_session(document_id, premade_session)
    if not premade_session:
        # TODO: pour plus tard, en récupérant l'historique de l'utilisateur
        #       et éventuellement ses préférences. Suite de questions recommandées
        #       par LLM, IA plus classique, ou bien créée et corrigée par des utilisateurs
        #       experts ou vérifiés.
        raise NotImplementedError

    questions_ids = PREMADE_QUESTIONS_BY_DOCUMENT_ID[document_id]
    conn = await get_db_connection()
    questions_tasks = [get_question_by_id(conn, question_id, include_answers=False) for question_id in questions_ids]
    questions = await asyncio.gather(*questions_tasks)

    # note: une liste par question, car une question peut avoir plusieurs chunks
    # TODO: il faudra ajouter avec le document la méthode de chunking utilisée,
    #       car pour le même document, il peut être découpé de plusieurs manières, donc avoir
    #       plusieurs chunks pour la même question.
    questions_chunks_tasks = [get_chunks_by_question_id(question_id, conn) for question_id in questions_ids]
    questions_chunks = await asyncio.gather(*questions_chunks_tasks)
    questions_texts = [question["content"] for question in questions]
    question_pages = [chunk[0]["num_page"] for chunk in questions_chunks]

    print(questions_texts)
    print(question_pages)
    session_manager.add_questions(session_id, questions_ids, questions_texts, question_pages)

    return session_manager.get_session_status(session_id)


@app.post("/api/sessions/message",
          response_model=SessionResponse)
async def submit_message(request: SessionMessage):
    """
    Ajoute un message à la conversation d'une session. L'agent analyse la réponse pour vérifier
    si c'est la réponse à la question en cours, ou une demande de contexte supplémentaire.
    """
    start_time = time.time()
    total_input_tokens = 0
    total_output_tokens = 0

    session_id = request.session_id
    user_message = request.user_message

    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")

    if not evaluators:
        logging.error("Evaluateurs non initialisés")
        raise HTTPException(status_code=500, detail="Evaluateurs non initialisés")

    current_question_id = session_manager.get_current_question_id(session_id)
    if not current_question_id:
        raise HTTPException(status_code=500, detail="Erreur détectée lors du traitement de la session")

    # récupérer la question et ses réponses
    question = await get_question_by_id(await get_db_connection(),
                                        current_question_id,
                                        include_answers=True)

    # vérification du type de message
    # -> Tuple[OutputSchema, TokenCountResult, int]
    result, token_count_result, output_tokens = monitor_agent_call(message_ev_agent,
                                                                   user_input=MessageTypeRequestInput(
                                                                              current_question=question["content"],
                                                                              user_message=user_message
                                                                   ),
                                                                   method = "run")
    message_type = result.message_type
    total_input_tokens += token_count_result.total
    total_output_tokens += output_tokens

    logging.info("Message type determined : {message_type}".format(message_type=message_type),)
    new_question = False
    is_finished = False
    message = ""
    match message_type:
        case "réponse":
            if not question["answers"]:
                raise HTTPException(status_code=500, detail="Pas de réponse prévue pour cette question...")
            # il peut y avoir plusieurs réponses, on ne garde que la
            # 1ère
            expected_answer = question["answers"][0]["content"]
            evaluation_input = EvaluateRequestInput(
                question=question['content'],
                expected_answer=expected_answer,
                user_answer=user_message
            )

            # note: les evaluators sont initialisés avec des clients async.
            # pour pouvoir effectuer ces appels en parallèle.
            evaluations = []
            """
            for evaluator in evaluators:
                evaluation, token_count_result, output_tokens = await monitor_agent_call_async(evaluator,
                                                                                         evaluation_input,
                                                                                         "run_async")
                total_input_tokens += token_count_result.total
                total_output_tokens += output_tokens
                evaluations.append(evaluation)
            print(evaluations)
            """
            coroutines = [
                monitor_agent_call_async(evaluator, evaluation_input, "run_async")
                for evaluator in evaluators
            ]

            eval_results = await asyncio.gather(*coroutines)
            for result in eval_results:
                evaluation, token_count_result, output_tokens = result
                evaluations.append(evaluation)
                total_input_tokens += token_count_result.total
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
                total_input_tokens += token_count_result.total
                total_output_tokens += output_tokens
            else:
                final_evaluation = evaluations[0]

            evaluation_result = from_AgentEvaluationResult_to_EvaluationResult(final_evaluation)
            user_response = UserResponse(
                question_id=current_question_id,
                question_text=question['content'],
                user_answer=user_message,
                date_sent=datetime.now(),
                evaluation=evaluation_result
            )

            #mettre à jour la session
            session_manager.add_response(session_id, user_response)

            if evaluation_result.score >= 7:
                # Si le score est suffisant, passer à la question suivante
                # peut également marquer la fin de la session si c'était la dernière qst
                session_manager.increment_current_index(session_id)
                is_finished = session_manager.is_finished(session_id)

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
    session_response = SessionResponse(
        session_status=session_manager.get_session_status(session_id),
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

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> SessionStatus:
    """
    Récupère l'état actuel d'une session.
    """
    return

@app.get("/api/sessions/export/{session_id}")
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
async def get_pdf(document_id: str):

    document_id = document_id.replace(".pdf", "")
    # note: pour l'instant, l'id du document est également son nom dans le dossier
    file_path = f"C:/Users/xenyi/Documents/Ressources-Pro/Thèse/M3C-documents/{document_id}.pdf"
    if not os.path.exists(file_path):
        print("file not found...")
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    return FileResponse(file_path, media_type="application/pdf")

@app.get("/api/documents", response_model=DocumentsListResponse, tags=["Documents"])
async def get_documents_list():
    """
    Récupère la liste de tous les documents disponibles dans la base de données.
    
    Returns:
        DocumentsListResponse: Liste des documents avec leurs métadonnées
    """
    try:
        # Connexion à la base de données
        conn = await get_db_connection()
        
        # Récupérer tous les documents
        documents = await get_all_documents(conn)
        
        # Fermer la connexion
        await conn.close()
        
        # Construire la réponse
        document_responses = []
        for doc in documents:
            document_responses.append(DocumentResponse(
                document_id=doc["document_id"],
                file_name=doc["file_name"],
                file_path=doc["file_path"],
                file_size=doc["file_size"],
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

import json
from datetime import datetime
from pathlib import Path

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
    print(torch.cuda.is_available())
    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        loop="asyncio"
    )
