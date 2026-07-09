"""
Router FastAPI pour les requêtes et l'indexation Solr.
"""
import os
import asyncio
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pysolr import Solr, SolrError
import json

# Import des modèles
from .models import (
    SolrIndexRequest,
    SolrIndexResponse,
    SolrIndexStatusResponse,
    SolrIndexJobListResponse,
    SolrIndexCancelResponse
)

# Import des services
from .services import (
    create_solr_indexing_job,
    get_solr_indexing_job,
    get_all_solr_indexing_jobs,
    cancel_solr_indexing_job,
    process_solr_indexing_job_job,
    clear_solr_index
)

core_name = "m3c_shard1_replica_n1"
# Import du gestionnaire SSE
from .sse_manager import sse_manager


# Modèle pour la requête Solr
class SolrQueryRequest(BaseModel):
    """Modèle de requête pour interroger Solr"""
    query: str = Field(..., description="Requête de recherche Solr (q parameter)", min_length=1)
    rows: int = Field(10, description="Nombre de résultats à retourner", ge=1, le=1000)
    start: int = Field(0, description="Index de départ pour la pagination", ge=0)
    filters: Optional[Dict[str, str]] = Field(
        None, 
        description="Filtres Solr (fq parameters) sous forme de dict {field: value}"
    )
    sort: Optional[str] = Field(
        None, 
        description="Tri des résultats (ex: 'score desc', 'date ascending')"
    )
    fields: Optional[List[str]] = Field(
        None, 
        description="Liste des champs à retourner (fl parameter)"
    )


# Modèle pour la réponse Solr
class SolrQueryResponse(BaseModel):
    """Modèle de réponse pour une requête Solr"""
    success: bool = Field(..., description="Indique si la requête a réussi")
    results: List[Dict[str, Any]] = Field(
        [], 
        description="Liste des documents trouvés"
    )
    num_found: int = Field(0, description="Nombre total de documents trouvés")
    start: int = Field(0, description="Index de départ de la pagination")
    query_time: int = Field(0, description="Temps d'exécution de la requête en ms")
    error: Optional[str] = Field(None, description="Message d'erreur si applicable")


# Initialisation du router
router = APIRouter(prefix="/api/solr", tags=["Solr", "Recherche", "Indexation"])


def get_solr_connection():
    """
    Crée une connexion à Solr.
    L'URL est lue depuis la variable d'environnement SOLR_URL.
    Default: http://localhost:8983/solr
    """
    solr_url = os.getenv("SOLR_URL", "http://localhost:8983/solr/"+core_name)
    return Solr(solr_url)


@router.post("/query",
             response_model=SolrQueryResponse,
             summary="Effectuer une requête Solr",
             description="Exécute une requête de recherche sur Solr et retourne les résultats")
async def query_solr(request: SolrQueryRequest):
    """
    Effectue une requête de recherche sur Solr.
    
    Args:
        request: SolrQueryRequest contenant la requête et les paramètres
        
    Returns:
        SolrQueryResponse avec les résultats de la recherche
        
    Raises:
        HTTPException: En cas d'erreur de connexion ou de requête
    """
    try:
        # Connexion à Solr
        solr = get_solr_connection()
        
        # Construction des paramètres de requête
        query_params = {
            "q": request.query,
            "rows": request.rows,
            "start": request.start,
        }
        
        # Ajouter les filtres si présents
        if request.filters:
            fq_params = []
            for field, value in request.filters.items():
                fq_params.append(f"{field}:{value}")
            query_params["fq"] = fq_params
        
        # Ajouter le tri si présent
        if request.sort:
            query_params["sort"] = request.sort
        
        # Ajouter les champs à retourner si présents
        if request.fields:
            query_params["fl"] = ",".join(request.fields)
        
        # Exécuter la requête
        results = solr.search(**query_params)
        
        # Formater la réponse
        response_results = []
        for doc in results.docs:
            response_results.append(dict(doc))
        
        return SolrQueryResponse(
            success=True,
            results=response_results,
            num_found=results.hits,
            start=request.start,
            query_time=results.qtime,
            error=None
        )
        
    except SolrError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur Solr: {str(e)}"
        )
    except ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Impossible de se connecter à Solr: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur inattendue: {str(e)}"
        )


# ============================================================================
# ROUTES D'INDEXATION SOLR
# ============================================================================

@router.post("/index/start",
             response_model=SolrIndexResponse,
             summary="Lancer un job d'indexation Solr",
             description="Crée et lance un nouveau job pour indexer des documents dans Solr")
async def start_solr_indexing_job(request: SolrIndexRequest):
    """
    Lance un job d'indexation Solr.
    
    Le job va :
    1. Se connecter à Solr (core spécifié ou par défaut 'm3c')
    2. Récupérer les documents depuis la base MySQL
    3. Formater chaque chunk pour Solr
    4. Indexer les documents par batches
    5. Optionnellement vider l'index avant (ATTENTION: clear_index=true supprime tout)
    
    Args:
        request: SolrIndexRequest avec les paramètres du job
        
    Returns:
        SolrIndexResponse avec l'ID du job créé
        
    Raises:
        HTTPException: En cas d'erreur de création du job
    """
    try:
        try:
            solr = get_solr_connection()
            print(solr)
            solr.ping()
        except Exception as e:
            print(e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Impossible de se connecter à Solr: {str(e)}"
            )

        response = await create_solr_indexing_job(request)

        asyncio.create_task(process_solr_indexing_job_job(response.job_id))
        
        return response
        
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du lancement du job: {str(e)}"
        )


@router.get("/index/status/{job_id}",
            response_model=SolrIndexStatusResponse,
            summary="Statut d'un job d'indexation Solr",
            description="Récupère le statut et la progression d'un job d'indexation")
async def get_solr_indexing_job_status(job_id: str):
    """
    Récupère le statut d'un job d'indexation Solr.
    
    Args:
        job_id: ID unique du job
        
    Returns:
        SolrIndexStatusResponse avec le statut et la progression
        
    Raises:
        HTTPException: Si le job n'est pas trouvé
    """
    job = await get_solr_indexing_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} non trouvé"
        )
    
    return job


@router.get("/index/jobs",
            response_model=SolrIndexJobListResponse,
            summary="Lister tous les jobs d'indexation Solr",
            description="Retourne la liste de tous les jobs d'indexation Solr")
async def list_solr_indexing_jobs(status_filter: Optional[str] = None):
    """
    Liste tous les jobs d'indexation Solr.
    
    Args:
        status_filter: Filtre optionnel par statut (pending, running, completed, failed, cancelled)
        
    Returns:
        SolrIndexJobListResponse avec la liste des jobs
    """
    jobs = await get_all_solr_indexing_jobs(status_filter)
    return SolrIndexJobListResponse(jobs=jobs, count=len(jobs))


@router.post("/index/{job_id}/cancel",
             response_model=SolrIndexCancelResponse,
             summary="Annuler un job d'indexation Solr",
             description="Annule un job d'indexation en cours")
async def cancel_solr_indexing_job_endpoint(job_id: str):
    """
    Annule un job d'indexation Solr.
    
    Args:
        job_id: ID du job à annuler
        
    Returns:
        SolrIndexCancelResponse avec le résultat de l'annulation
        
    Raises:
        HTTPException: Si le job n'est pas trouvé ou ne peut pas être annulé
    """
    success, message, previous_status = await cancel_solr_indexing_job(job_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return SolrIndexCancelResponse(
        success=True,
        job_id=job_id,
        message=message,
        previous_status=previous_status
    )


@router.post("/index/{solr_core}/clear",
             summary="Vider un index Solr",
             description="Supprime tous les documents d'un core Solr (ATTENTION: opération destructive)")
async def clear_solr_index_endpoint(solr_core: str, confirm: bool = False):
    """
    Vide complètement un core Solr.
    
    ⚠️ ATTENTION: Cette opération supprime TOUS les documents du core spécifié !
    
    Args:
        solr_core: Nom du core Solr à vider
        confirm: Doit être True pour confirmer l'opération
        
    Returns:
        Message de confirmation ou d'erreur
        
    Raises:
        HTTPException: Si la confirmation est manquante ou si erreur
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La confirmation est requise. Ajoutez ?confirm=true à l'URL ou confirmez dans le body"
        )
    
    try:
        success, message = await clear_solr_index(solr_core)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message
            )
        
        return {"success": True, "message": message}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du vidage: {str(e)}"
        )


@router.get("/index/{job_id}/events",
            summary="Flux SSE pour un job d'indexation",
            description="Flux Server-Sent Events pour suivre la progression d'un job en temps réel")
async def solr_indexing_job_events(job_id: str, request: Request):
    """
    Flux SSE pour recevoir des notifications en temps réel sur un job d'indexation Solr.
    
    Les événements incluent:
    - job_started: Le job a commencé
    - progress: Progression du traitement
    - index_cleared: L'index a été vidé (si clear_index=true)
    - job_completed: Le job est terminé avec succès
    - job_failed: Le job a échoué
    
    Args:
        job_id: ID du job à surveiller
        request: Objet Request FastAPI
        
    Returns:
        StreamingResponse avec le flux d'événements
    """
    # Vérifier que le job existe
    job = await get_solr_indexing_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} non trouvé"
        )
    
    # Connexion au flux SSE
    queue = await sse_manager.connect(job_id)
    
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                    
                event = await queue.get()
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
        except asyncio.CancelledError:
            await sse_manager.disconnect(job_id, queue)
            raise
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
