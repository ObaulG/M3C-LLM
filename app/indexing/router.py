"""
Router FastAPI pour la gestion des jobs d'indexation.
"""
from urllib import request

from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import StreamingResponse
from typing import Optional, List
from datetime import datetime
import uuid
import asyncio
import json

import database
from app.embedders import get_embedder_instance

from database.database import VALID_TEXT_RESOURCE_ID
from .services import (
    process_pdf_indexing_job,
    create_indexing_job,
    get_latest_job_by_type,
    update_indexing_job,
    get_indexing_job
)

from .models import (
    IndexJobRequest,
    IndexJobStatusResponse,
    IndexJobControlResponse,
    IndexJobListResponse, IndexDocumentsResponse, IndexDocumentsRequest
)
from .services import process_pdf_indexing_job, split_text_into_chunks
from database.database import insert_chunks, insert_chunk_embeddings_batch_qdrant
from .sse_manager import sse_manager

router = APIRouter(prefix="/api/admin/documents/index", tags=["Admin", "Indexation"])




@router.post("",
          response_model=IndexDocumentsResponse,
          tags=["Admin"])
async def index_existing_documents(request: IndexDocumentsRequest):
    """
    Indexe des documents EXISTANTS dans la base de données.

    Selon le type d'indexation:
    - 'all-metadata': Indexe uniquement les métadonnées des documents (file_name, file_path, etc.)
    - 'all-with-text': Découpe le contenu extrait (extracted_text) en chunks et indexe chaque chunk
    - 'pdf-from-m3c': Télécharge les PDFs depuis M3C, découpe et indexe (via job asynchrone)

    Les documents doivent déjà exister dans la base de données pour 'all-metadata' et 'all-with-text'.
    Pour 'pdf-from-m3c', les PDFs sont téléchargés depuis la base M3C.

    Args:
        request: IndexDocumentsRequest avec indexation_type, chunk_size, chunk_overlap, embedder_name

    Returns:
        IndexDocumentsResponse avec le résultat de l'indexation
    """
    print("Requête d'indexation")
    print(request)

    # Vérifier s'il existe un job en cours non terminé (état running
    current_job = get_latest_job_by_type(
        request.indexation_type,
        exclude_status=["completed", "cancelled"]
    )

    if not current_job:
        current_job_id = create_indexing_job(
            job_type=request.indexation_type,
            parameters={
                "chunk_size": request.chunk_size,
                "chunk_overlap": request.chunk_overlap,
                "embedder_name": request.embedder_name,
            }
        )
        current_job = get_indexing_job(current_job_id)
    current_job_id = current_job["job_id"]


    print("current_job_id: ", current_job_id)
    try:
        # Démarrer le traitement en arrière-plan
        import asyncio as asyncio_mod

        if request.indexation_type == "pdf-from-m3c":
            asyncio_mod.create_task(process_pdf_indexing_job(
                current_job_id,
                request.chunk_size,
                request.chunk_overlap,
                request.embedder_name,
            ))
        elif request.indexation_type == "all-metadata":
            raise NotImplementedError
        elif request.indexation_type == "all-with-text":
            raise NotImplementedError
        else:
            raise NotImplementedError

        return IndexDocumentsResponse(
            success=True,
            processed_documents=0,
            chunks_created=0,
            embeddings_generated=0,
            chunks_by_document={},
            errors=[f"Job {current_job_id} démarré. Utilisez GET /api/admin/documents/index/job/{current_job_id}/status"],
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        print(f"Erreur job pdf-from-m3c: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur: {str(e)}"
        )


@router.post("/job/start",
          response_model=IndexJobControlResponse,
          summary="Démarrer un job d'indexation")
async def start_indexing_job_endpoint(request: IndexJobRequest):
    """
    Démarre un nouveau job d'indexation de PDFs depuis M3C.
    """
    from database.database import VALID_TEXT_RESOURCE_ID
    from .services import (
        process_pdf_indexing_job,
        create_indexing_job,
        get_latest_job_by_type,
        update_indexing_job,
        get_indexing_job
    )
    
    try:
        existing_job = get_latest_job_by_type(
            "pdf-from-m3c",
            exclude_status=["completed", "cancelled"]
        )
        
        if existing_job and not request.force_restart:
            return IndexJobControlResponse(
                success=False,
                job_id=existing_job["job_id"],
                message=f"Un job est déjà en cours (ID: {existing_job['job_id']})",
                job_status=IndexJobStatusResponse(**existing_job)
            )
        
        if existing_job and request.force_restart:
            update_indexing_job(
                existing_job["job_id"],
                status="cancelled",
                error_message="Redémarré manuellement par l'utilisateur"
            )
        
        job_id = create_indexing_job(
            job_type="pdf-from-m3c",
            parameters={
                "chunk_size": request.chunk_size,
                "chunk_overlap": request.chunk_overlap
            }
        )
        print("job_id: ", job_id)
        asyncio.create_task(process_pdf_indexing_job(
            job_id,
            request.chunk_size,
            request.chunk_overlap
        ))
        
        # Récupérer le job pour construire le job_status
        job = get_indexing_job(job_id)
        job_status = IndexJobStatusResponse(**job) if job else IndexJobStatusResponse(
            job_id=job_id,
            job_type="pdf-from-m3c",
            status="pending",
            total_items=len(VALID_TEXT_RESOURCE_ID),
            processed_items=0,
            progress={},
            parameters={"chunk_size": request.chunk_size, "chunk_overlap": request.chunk_overlap},
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            error_message=None
        )
        
        return IndexJobControlResponse(
            success=True,
            job_id=job_id,
            message=f"Job {job_id} démarré en arrière-plan",
            job_status=job_status
        )
        
    except Exception as e:
        print(f"Erreur démarrage job: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du démarrage du job: {str(e)}"
        )


@router.get("/job/{job_id}/status", 
         response_model=IndexJobStatusResponse,
         summary="Statut d'un job")
async def get_job_status(job_id: str):
    """Récupère le statut d'un job d'indexation."""
    from .services import get_indexing_job
    
    try:
        job = get_indexing_job(job_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} non trouvé"
            )
        
        return IndexJobStatusResponse(**job)
        
    except Exception as e:
        print(f"Erreur récupération statut job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération du statut: {str(e)}"
        )


@router.get("/jobs",
         response_model=IndexJobListResponse,
         summary="Lister tous les jobs")
async def list_indexing_jobs(status_filter: Optional[str] = None):
    """Liste tous les jobs d'indexation."""
    from .services import get_all_indexing_jobs
    
    try:
        jobs = get_all_indexing_jobs(status_filter)
        
        return IndexJobListResponse(
            jobs=[IndexJobStatusResponse(**job) for job in jobs],
            count=len(jobs)
        )
        
    except Exception as e:
        print(f"Erreur liste jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des jobs: {str(e)}"
        )


@router.get("/count",
         response_model=dict,
         summary="Compter les documents à indexer")
async def get_indexing_count():
    """Retourne le nombre et identifiants de documents à indexer pour pdf-from-m3c."""
    from database.database import VALID_TEXT_RESOURCE_ID
    return {
        "pdf_from_m3c_count": len(VALID_TEXT_RESOURCE_ID),
        "valid_resource_ids": VALID_TEXT_RESOURCE_ID
    }


@router.post("/job/{job_id}/cancel",
          response_model=IndexJobControlResponse,
          summary="Annuler un job")
async def cancel_indexing_job(job_id: str):
    """Annule un job d'indexation en cours."""
    from .services import get_indexing_job, update_indexing_job
    
    try:
        job = get_indexing_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} non trouvé"
            )
        
        if job["status"] in ["completed", "cancelled"]:
            return IndexJobControlResponse(
                success=False,
                job_id=job_id,
                message=f"Le job {job_id} ne peut pas être annulé (statut: {job['status']})",
                job_status=IndexJobStatusResponse(**job)
            )
        
        update_indexing_job(
            job_id,
            status="cancelled",
            error_message="Annulé manuellement par l'utilisateur"
        )
        
        job["status"] = "cancelled"
        job["error_message"] = "Annulé manuellement par l'utilisateur"
        
        return IndexJobControlResponse(
            success=True,
            job_id=job_id,
            message=f"Job {job_id} annulé avec succès",
            job_status=IndexJobStatusResponse(**job)
        )
        
    except Exception as e:
        print(f"Erreur annulation job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'annulation du job: {str(e)}"
        )


@router.get("/job/{job_id}/events",
         response_model=None,
         summary="Flux SSE pour les événements d'un job")
async def job_events(job_id: str, request: Request):
    """
    Endpoint Server-Sent Events pour recevoir des notifications en temps réel
    sur l'état d'un job d'indexation.
    """
    queue = await sse_manager.connect(job_id)
    
    async def event_generator():
        try:
            while True:
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
