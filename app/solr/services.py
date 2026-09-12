"""
Services pour l'indexation Solr.
"""
import os
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from pysolr import Solr, SolrError

from database.database import (
    VALID_TEXT_RESOURCE_ID,
    get_db_connection,
    get_resource_full_metadata,
    get_pdf_url_for_resource,
)
from .models import SolrIndexRequest, SolrIndexResponse, SolrIndexStatusResponse

# Configuration Solr
SOLR_URL = os.getenv("SOLR_URL", "http://localhost:8983/solr")


def get_solr_connection(core: str = None):
    """
    Crée une connexion à un core Solr spécifique.
    
    Args:
        core: Nom du core Solr (ex: 'm3c'). Si None, utilise le core par défaut.
    
    Returns:
        Instance Solr connectée au core spécifié
    """
    if core:
        solr_url = f"{SOLR_URL}/{core}"
    else:
        solr_url = SOLR_URL
    return Solr(solr_url)


async def create_solr_indexing_job(request: SolrIndexRequest) -> SolrIndexResponse:
    """
    Crée un nouveau job d'indexation Solr.
    
    Args:
        request: SolrIndexRequest avec les paramètres d'indexation
    
    Returns:
        SolrIndexResponse avec l'ID du job créé
    """
    from app.jobs.manager import create_job
    
    # Déterminer les resource_ids à indexer
    resource_ids = request.resource_ids or VALID_TEXT_RESOURCE_ID
    total_items = len(resource_ids)
    
    # Créer le job via le gestionnaire central
    job_id = create_job(
        job_type="solr-indexing",
        document_categories=["solr"],
        total_items=total_items,
        parameters={
            "solr_core": request.solr_core,
            "batch_size": request.batch_size,
            "resource_ids": resource_ids,
            "commit": request.commit,
            "clear_index": request.clear_index
        }
    )
    
    return SolrIndexResponse(
        success=True,
        job_id=job_id,
        message=f"Job d'indexation Solr {job_id} créé avec succès",
        total_items=total_items,
        solr_core=request.solr_core,
        status="pending",
        created_at=datetime.now().isoformat()
    )


async def get_solr_indexing_job(job_id: str) -> Optional[SolrIndexStatusResponse]:
    """
    Récupère un job d'indexation Solr.
    
    Args:
        job_id: ID du job à récupérer
    
    Returns:
        SolrIndexStatusResponse ou None si non trouvé
    """
    from app.jobs.manager import get_job
    
    job = get_job(job_id)
    if not job:
        return None
    
    return SolrIndexStatusResponse(
        job_id=job["job_id"],
        job_type=job["job_type"],
        status=job["status"],
        total_items=job.get("total_items", 0),
        processed_items=job.get("processed_items", 0),
        progress=job.get("progress", {}),
        error_message=job.get("error_message"),
        parameters=job.get("parameters", {}),
        created_at=job["created_at"],
        updated_at=job["updated_at"]
    )


async def get_all_solr_indexing_jobs(status_filter: Optional[str] = None) -> List[SolrIndexStatusResponse]:
    """
    Récupère tous les jobs d'indexation Solr.
    
    Args:
        status_filter: Filtre optionnel par statut
    
    Returns:
        Liste de SolrIndexStatusResponse
    """
    from app.jobs.manager import get_jobs_by_type
    
    jobs = get_jobs_by_type("solr-indexing")
    
    if status_filter:
        jobs = [job for job in jobs if job.get("status") == status_filter]
    
    return [
        SolrIndexStatusResponse(
            job_id=job["job_id"],
            job_type=job["job_type"],
            status=job["status"],
            total_items=job.get("total_items", 0),
            processed_items=job.get("processed_items", 0),
            progress=job.get("progress", {}),
            error_message=job.get("error_message"),
            parameters=job.get("parameters", {}),
            created_at=job["created_at"],
            updated_at=job["updated_at"]
        )
        for job in jobs
    ]


async def cancel_solr_indexing_job(job_id: str) -> Tuple[bool, str, str]:
    """
    Annule un job d'indexation Solr.
    
    Args:
        job_id: ID du job à annuler
    
    Returns:
        Tuple: (success, message, previous_status)
    """
    from app.jobs.manager import get_job, update_job
    
    job = get_job(job_id)
    if not job:
        return False, f"Job {job_id} non trouvé", ""
    
    previous_status = job["status"]
    
    if previous_status in ["completed", "cancelled"]:
        return False, f"Le job {job_id} ne peut pas être annulé (statut: {previous_status})", previous_status
    
    update_job(
        job_id,
        status="cancelled",
        error_message="Annulé manuellement par l'utilisateur"
    )
    
    return True, f"Job {job_id} annulé avec succès", previous_status


def format_document_for_solr(resource_id: int, metadata: Optional[Dict] = None) -> Dict:
    """
    Formate un document pour l'indexation Solr basé sur ses métadonnées.
    
    Chaque document est indexé comme un document Solr unique avec :
    - Une concaténation de toutes les métadonnées dans les champs 'content' et 'text' (pour la recherche)
    - Les métadonnées individuelles du document pour le faceting et les filtres
    
    Args:
        resource_id: ID de la ressource
        metadata: Métadonnées du document
    
    Returns:
        Dictionary formaté pour Solr
    """
    # Créer un texte concaténé à partir de toutes les métadonnées
    metadata_parts = []
    
    if metadata:
        if metadata.get("title"):
            metadata_parts.append(f"title: {metadata['title']}")
        if metadata.get("creator"):
            metadata_parts.append(f"author: {metadata['creator']}")
            metadata_parts.append(f"creator: {metadata['creator']}")
        if metadata.get("description"):
            metadata_parts.append(f"description: {metadata['description']}")
        if metadata.get("publisher"):
            metadata_parts.append(f"publisher: {metadata['publisher']}")
        if metadata.get("contributor"):
            metadata_parts.append(f"contributor: {metadata['contributor']}")
        if metadata.get("date"):
            metadata_parts.append(f"date: {metadata['date']}")
        if metadata.get("type"):
            metadata_parts.append(f"type: {metadata['type']}")
        if metadata.get("language"):
            metadata_parts.append(f"language: {metadata['language']}")
        if metadata.get("subjects") and isinstance(metadata["subjects"], list):
            subjects_str = " ".join(metadata["subjects"])
            metadata_parts.append(f"subjects: {subjects_str}")
        if metadata.get("abstract"):
            metadata_parts.append(f"abstract: {metadata['abstract']}")
    
    # Le contenu principal est la concaténation des métadonnées
    metadata_text = " \n ".join(metadata_parts)
    
    doc = {
        "id": f"solr_{resource_id}",
        "resource_id": resource_id,
        "resource_id_str": str(resource_id),
        "content": metadata_text,
        "text": metadata_text,  # Champ standard pour la recherche full-text dans Solr
        "_text_": metadata_text,  # Champ de copyField dans certains schemas
        "type": "document",
        "source_type": "metadata",
    }
    
    # Ajouter les métadonnées individuelles pour le faceting et les filtres
    if metadata:
        if "title" in metadata:
            doc["title"] = metadata["title"]
            doc["title_s"] = metadata["title"]  # String field pour faceting
        if "creator" in metadata:
            doc["author"] = metadata["creator"]
            doc["author_s"] = metadata["creator"]
            doc["creator"] = metadata["creator"]
        if "description" in metadata:
            doc["description"] = metadata["description"]
            doc["description_t"] = metadata["description"]  # Text field pour recherche
        if "publisher" in metadata:
            doc["publisher"] = metadata["publisher"]
            doc["publisher_s"] = metadata["publisher"]
        if "contributor" in metadata:
            doc["contributor"] = metadata["contributor"]
            doc["contributor_s"] = metadata["contributor"]
        if "date" in metadata:
            doc["date"] = metadata["date"]
            doc["date_dt"] = metadata["date"]  # Date field
        if "type" in metadata:
            doc["document_type"] = metadata["type"]
            doc["document_type_s"] = metadata["type"]
        if "subjects" in metadata and metadata["subjects"]:
            doc["subjects"] = metadata["subjects"]
            # Solr peut indexer des tableaux, mais on les rejoint pour la recherche
            if isinstance(metadata["subjects"], list):
                doc["subjects_t"] = " ".join(metadata["subjects"])
        if "language" in metadata:
            doc["language"] = metadata["language"]
            doc["language_s"] = metadata["language"]
        if "abstract" in metadata:
            doc["abstract"] = metadata["abstract"]
            doc["abstract_t"] = metadata["abstract"]
    
    # Ajouter un timestamp
    doc["indexed_at"] = datetime.now().isoformat()
    doc["indexed_at_dt"] = datetime.now().isoformat()
    
    return doc



async def index_document_to_solr(
    solr_core: str,
    resource_id: int,
    commit: bool = True
) -> Tuple[bool, int, List[str]]:
    """
    Indexe un seul document (basé sur ses métadonnées) dans Solr.
    
    Args:
        solr_core: Nom du core Solr
        resource_id: ID de la ressource à indexer
        commit: Si True, effectue un commit après l'indexation
    
    Returns:
        Tuple: (success, documents_indexed, errors)
              documents_indexed sera toujours 1 (un document par resource_id)
    """
    solr = get_solr_connection(solr_core)
    errors = []
    documents_indexed = 0
    
    try:
        # Récupérer les métadonnées du document
        async with await get_db_connection() as conn:
            metadata = await get_resource_full_metadata(conn, resource_id)

        
        if not metadata:
            errors.append(f"Aucune métadonnée trouvée pour resource_id {resource_id}")
            return False, 0, errors
        
        # Formater le document basé sur les métadonnées
        try:
            formatted_doc = format_document_for_solr(resource_id, metadata)
        except Exception as e:
            errors.append(f"Resource {resource_id}: Erreur de formatage - {str(e)}")
            return False, 0, errors
        
        # Indexer le document
        try:
            solr.add([formatted_doc], commit=commit)
            documents_indexed = 1
        except SolrError as e:
            errors.append(f"Erreur Solr lors de l'ajout: {str(e)}")
            return False, 0, errors
        
        return True, documents_indexed, errors
        
    except Exception as e:
        errors.append(f"Erreur globale pour resource_id {resource_id}: {str(e)}")
        return False, 0, errors


async def clear_solr_index(solr_core: str) -> Tuple[bool, str]:
    """
    Efface tous les documents d'un core Solr.
    
    Args:
        solr_core: Nom du core à vider
    
    Returns:
        Tuple: (success, message)
    """
    try:
        solr = get_solr_connection(solr_core)
        solr.delete(q="*:*")
        return True, f"Index {solr_core} vidé avec succès"
    except SolrError as e:
        return False, f"Erreur lors du vidage: {str(e)}"
    except Exception as e:
        return False, f"Erreur inattendue: {str(e)}"


async def process_solr_indexing_job_job(job_id: str):
    """
    Traite un job d'indexation Solr en arrière-plan.
    
    Args:
        job_id: ID du job à traiter
    """
    from app.jobs.manager import get_job, update_job
    from app.solr.sse_manager import sse_manager
    
    job = get_job(job_id)
    if not job:
        print(f"Job {job_id} non trouvé")
        return
    
    parameters = job.get("parameters", {})
    solr_core = parameters.get("solr_core", "m3c")
    batch_size = parameters.get("batch_size", 50)
    resource_ids = parameters.get("resource_ids", VALID_TEXT_RESOURCE_ID)
    commit = parameters.get("commit", True)
    clear_index = parameters.get("clear_index", False)
    
    # Mettre à jour le statut en running
    update_job(job_id, status="running", processed_items=0)
    await sse_manager.send_event(job_id, "job_started", {
        "job_id": job_id,
        "status": "running",
        "total_items": len(resource_ids)
    })
    
    total_resources = len(resource_ids)
    processed_count = 0
    errors = []
    progress = {}
    
    try:
        # Optionnellement vider l'index
        if clear_index:
            success, message = await clear_solr_index(solr_core)
            if not success:
                errors.append(f"Échec du vidage de l'index: {message}")
                update_job(job_id, status="failed", error_message="; ".join(errors))
                await sse_manager.send_event(job_id, "job_failed", {
                    "error": message
                })
                return
            await sse_manager.send_event(job_id, "index_cleared", {
                "message": message
            })
        
        # Traiter les documents par batches
        for i in range(0, len(resource_ids), batch_size):
            batch = resource_ids[i:i + batch_size]
            batch_errors = []
            batch_processed = 0
            
            for resource_id in batch:
                resource_id_str = str(resource_id)
                progress[resource_id_str] = {
                    "status": "processing",
                    "started_at": datetime.now().isoformat()
                }
                update_job(job_id, status="running", progress=progress, processed_items=processed_count)
                
                try:
                    success, documents_indexed, resource_errors = await index_document_to_solr(
                        solr_core, resource_id, commit=commit
                    )
                    
                    if success:
                        progress[resource_id_str] = {
                            "status": "completed",
                            "documents_indexed": documents_indexed,
                            "processed_at": datetime.now().isoformat()
                        }
                        batch_processed += documents_indexed
                    else:
                        progress[resource_id_str] = {
                            "status": "failed",
                            "errors": resource_errors,
                            "processed_at": datetime.now().isoformat()
                        }
                        batch_errors.extend(resource_errors)
                    
                except Exception as e:
                    progress[resource_id_str] = {
                        "status": "failed",
                        "error": str(e),
                        "processed_at": datetime.now().isoformat()
                    }
                    batch_errors.append(f"Resource {resource_id}: {str(e)}")
                
                processed_count += 1
                await sse_manager.send_event(job_id, "progress", {
                    "processed": processed_count,
                    "total": total_resources,
                    "current_resource": resource_id,
                    "batch_errors": batch_errors
                })
            
            # Commit après chaque batch si demandé
            if commit:
                try:
                    solr = get_solr_connection(solr_core)
                    solr.commit()
                except Exception as e:
                    errors.append(f"Erreur de commit: {str(e)}")
        
        # Statut final
        all_errors = errors + batch_errors
        status = "completed" if processed_count == total_resources and not all_errors else "failed"
        error_msg = "; ".join(all_errors) if all_errors else None
        
        update_job(
            job_id, 
            status=status,
            progress=progress,
            processed_items=processed_count,
            error_message=error_msg
        )
        
        await sse_manager.send_event(job_id, "job_completed", {
            "job_id": job_id,
            "status": status,
            "processed_items": processed_count,
            "total_items": total_resources,
            "errors": all_errors
        })
        
    except Exception as e:
        error_msg = str(e)
        update_job(job_id, status="failed", error_message=error_msg, progress=progress, processed_items=processed_count)
        await sse_manager.send_event(job_id, "job_failed", {
            "error": error_msg
        })
