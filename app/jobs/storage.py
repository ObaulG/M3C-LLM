"""
Stockage unifié des jobs.

Ce module gère la persistance des jobs dans un fichier JSON central.
"""
import json
from pathlib import Path
from typing import Dict

# Fichier central de stockage de tous les jobs
JOBS_FILE = Path("app/jobs/jobs.json")


def _ensure_jobs_file():
    """Crée le fichier jobs.json s'il n'existe pas."""
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not JOBS_FILE.exists():
        with open(JOBS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2)


def load_all_jobs() -> Dict[str, dict]:
    """
    Charge tous les jobs depuis le fichier JSON.
    
    Returns:
        Dictionnaire de tous les jobs (job_id -> job_data)
    """
    _ensure_jobs_file()
    try:
        with open(JOBS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_all_jobs(jobs: Dict[str, dict]) -> None:
    """
    Sauvegarde tous les jobs dans le fichier JSON.
    
    Args:
        jobs: Dictionnaire de jobs à sauvegarder
    """
    _ensure_jobs_file()
    with open(JOBS_FILE, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)


def save_job(job_id: str, job_data: dict) -> None:
    """
    Sauvegarde un job individuel.
    
    Args:
        job_id: ID du job
        job_data: Données du job
    """
    jobs = load_all_jobs()
    jobs[job_id] = job_data
    save_all_jobs(jobs)


def delete_job(job_id: str) -> bool:
    """
    Supprime un job.
    
    Args:
        job_id: ID du job à supprimer
        
    Returns:
        True si le job a été supprimé, False s'il n'existait pas
    """
    jobs = load_all_jobs()
    if job_id in jobs:
        del jobs[job_id]
        save_all_jobs(jobs)
        return True
    return False
