"""
Gestionnaire central de jobs.

Ce module fournit une API unifiée pour créer, lire, mettre à jour et supprimer
 des jobs de n'importe quel type.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from .storage import load_all_jobs, save_job, save_all_jobs, delete_job


def create_job(job_type: str, document_categories: list = None, **kwargs) -> str:
    """
    Crée un nouveau job.
    
    Args:
        job_type: Type de tâche (ex: 'indexing', 'chunking', 'qa-generation')
        document_categories: Liste des catégories de documents concernés
            (ex: ["pdf-from-m3c"], ["all-metadata", "all-with-text"])
        **kwargs: Paramètres spécifiques au type de job
            - total_items: Nombre total d'éléments (pour indexing)
            - total_documents: Nombre total de documents (pour qa-generation)
            - parameters: Dictionnaire de paramètres du job
            - etc.
    
    Returns:
        job_id: L'ID unique du job créé
    """
    job_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    # Structure de base commune à tous les jobs
    job = {
        "job_id": job_id,
        "job_type": job_type,
        "document_categories": document_categories or [],
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "parameters": kwargs.get("parameters", {}),
        "progress": {},
        "error_message": None
    }
    
    # Ajouter des champs spécifiques selon le type de tâche
    if job_type in ["indexing", "chunking"]:
        # Jobs d'indexation/chunking
        job.update({
            "total_items": kwargs.get("total_items", 0),
            "processed_items": 0,
            "id_embeddings_missing": []
        })
    elif job_type == "qa-generation":
        # Jobs de génération de questions
        job.update({
            "total_documents": kwargs.get("total_documents", 0),
            "processed_documents": 0,
            "errors": []
        })
    
    save_job(job_id, job)
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    """
    Récupère un job par son ID.
    
    Args:
        job_id: L'ID du job à récupérer
        
    Returns:
        Le job sous forme de dict, ou None s'il n'existe pas
    """
    jobs = load_all_jobs()
    return jobs.get(job_id)


def get_jobs_by_type(job_type: str) -> List[dict]:
    """
    Récupère tous les jobs d'un type donné.
    
    Args:
        job_type: Type de job à filtrer
        
    Returns:
        Liste des jobs correspondants
    """
    jobs = load_all_jobs()
    return [job for job in jobs.values() if job.get("job_type") == job_type]


def get_all_jobs() -> List[dict]:
    """
    Récupère tous les jobs.
    
    Returns:
        Liste de tous les jobs
    """
    return list(load_all_jobs().values())


def get_latest_job(job_type: str, exclude_status: List[str] = None) -> Optional[dict]:
    """
    Récupère le job le plus récent d'un type donné.
    
    Args:
        job_type: Type de job à filtrer
        exclude_status: Liste des statuts à exclure (optionnel)
        
    Returns:
        Le job le plus récent sous forme de dict, ou None si aucun trouvé
    """
    jobs = [j for j in get_jobs_by_type(job_type) 
             if exclude_status is None or j.get("status") not in exclude_status]
    
    if not jobs:
        return None
    
    return max(jobs, key=lambda j: j.get("created_at", ""))


def update_job(job_id: str, **kwargs) -> bool:
    """
    Met à jour un job existant.
    
    Args:
        job_id: L'ID du job à mettre à jour
        **kwargs: Champs à mettre à jour (status, progress, processed_items, etc.)
        
    Returns:
        True si la mise à jour a réussi, False sinon
    """
    jobs = load_all_jobs()
    
    if job_id not in jobs:
        return False
    
    job = jobs[job_id]
    job["updated_at"] = datetime.now().isoformat()
    
    # Mettre à jour tous les champs fournis
    for key, value in kwargs.items():
        if value is not None:
            job[key] = value
    
    save_all_jobs(jobs)
    return True


# Alias pour la compatibilité avec l'ancien code
def get_latest_job_by_type(job_type: str, exclude_status: List[str] = None) -> Optional[dict]:
    """Alias pour get_latest_job."""
    return get_latest_job(job_type, exclude_status)
