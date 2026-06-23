"""
Script de migration vers la nouvelle nomenclature des jobs.

Ancien format :
  job_type = "pdf-from-m3c" ou "question_generation"

Nouveau format :
  job_type = "indexing" ou "qa-generation"
  document_categories = ["pdf-from-m3c"] ou ["validated-documents"]
"""
import json
from pathlib import Path

JOBS_FILE = Path("app/jobs/jobs.json")


def load_jobs():
    """Charge les jobs depuis le fichier."""
    if not JOBS_FILE.exists():
        return {}
    try:
        with open(JOBS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_jobs(jobs):
    """Sauvegarde les jobs dans le fichier."""
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(JOBS_FILE, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)


def migrate_nomenclature():
    """Applique la nouvelle nomenclature à tous les jobs."""
    jobs = load_jobs()
    
    print(f"Migration de {len(jobs)} jobs...")
    
    migration_map = {
        # Ancien job_type -> (nouveau job_type, document_categories)
        "pdf-from-m3c": ("indexing", ["pdf-from-m3c"]),
        "all-metadata": ("indexing", ["all-metadata"]),
        "all-with-text": ("indexing", ["all-with-text"]),
        "question_generation": ("qa-generation", ["validated-documents"]),
    }
    
    migrated_count = 0
    for job_id, job in jobs.items():
        old_job_type = job.get("job_type", "")
        
        if old_job_type in migration_map:
            new_job_type, doc_categories = migration_map[old_job_type]
            job["job_type"] = new_job_type
            job["document_categories"] = doc_categories
            migrated_count += 1
            print(f"  Migré job {job_id[:8]}... : {old_job_type} -> {new_job_type} + {doc_categories}")
        else:
            # Si le job_type n'est pas dans la map, on ajoute document_categories vide
            if "document_categories" not in job:
                job["document_categories"] = []
            print(f"  Job {job_id[:8]}... : type inconnu '{old_job_type}', document_categoriesté vide")
    
    save_jobs(jobs)
    print(f"\nMigration terminée ! {migrated_count}/{len(jobs)} jobs migrés.")
    return migrated_count


if __name__ == "__main__":
    migrate_nomenclature()
