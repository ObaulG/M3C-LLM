"""
Module central de gestion des jobs.

Ce module fournit une gestion unifiée pour tous les types de jobs de l'application.
"""

from .manager import (
    create_job,
    get_job,
    get_jobs_by_type,
    get_all_jobs,
    get_latest_job,
    update_job,
    delete_job,
)

from .storage import (
    load_all_jobs,
    save_all_jobs,
    JOBS_FILE,
)

__all__ = [
    "create_job",
    "get_job",
    "get_jobs_by_type",
    "get_all_jobs",
    "get_latest_job",
    "update_job",
    "delete_job",
    "load_all_jobs",
    "save_all_jobs",
    "JOBS_FILE",
]
