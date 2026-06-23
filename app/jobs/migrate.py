"""
Script de migration des anciens fichiers jobs.json vers le nouveau système unifié.

Ce script fusionne les fichiers:
- app/indexing/jobs.json
- app/question-answer/jobs.json

Dans le nouveau fichier:
- app/jobs/jobs.json
"""
import json
from pathlib import Path
from typing import Dict, Any

# Chemins des fichiers
OLD_INDEXING_JOBS = Path("app/indexing/jobs.json")
OLD_QA_JOBS = Path("app/question-answer/jobs.json")
NEW_JOBS = Path("app/jobs/jobs.json")


def load_json_file(path: Path) -> Dict[str, Any]:
    """Charge un fichier JSON."""
    if not path.exists():
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def migrate_jobs():
    """Migration des jobs vers le nouveau système."""
    print("Début de la migration des jobs...")
    
    # Charger les anciens jobs
    indexing_jobs = load_json_file(OLD_INDEXING_JOBS)
    qa_jobs = load_json_file(OLD_QA_JOBS)
    
    print(f"Jobs d'indexation trouvés: {len(indexing_jobs)}")
    print(f"Jobs de question-answer trouvés: {len(qa_jobs)}")
    
    # Fusionner tous les jobs
    all_jobs = {}
    all_jobs.update(indexing_jobs)
    all_jobs.update(qa_jobs)
    
    # Normaliser les jobs pour le nouveau format
    # Les jobs d'indexation ont déjà une structure compatible
    # Les jobs de question-answer devront être adaptés si nécessaire
    normalized_jobs = {}
    for job_id, job in all_jobs.items():
        # Ajouter job_type si absent (pour compatibilité ascendante)
        if "job_type" not in job:
            # Déterminer le type à partir du contexte
            if "total_documents" in job:
                job["job_type"] = "question_generation"
            else:
                job["job_type"] = "unknown"
        
        # S'assurer que tous les champs requis sont présents
        if "parameters" not in job:
            job["parameters"] = {}
        if "progress" not in job:
            job["progress"] = {}
        if "error_message" not in job:
            job["error_message"] = None
        
        normalized_jobs[job_id] = job
    
    print(f"Total jobs à migrer: {len(normalized_jobs)}")
    
    # Sauvegarder dans le nouveau fichier
    NEW_JOBS.parent.mkdir(parents=True, exist_ok=True)
    with open(NEW_JOBS, 'w', encoding='utf-8') as f:
        json.dump(normalized_jobs, f, indent=2, ensure_ascii=False)
    
    print(f"Migration terminée ! {len(normalized_jobs)} jobs sauvegardés dans {NEW_JOBS}")
    
    # Créer des backups des anciens fichiers
    backup_dir = Path("app/jobs/backups")
    backup_dir.mkdir(exist_ok=True)
    
    import shutil
    import datetime
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if OLD_INDEXING_JOBS.exists():
        backup_path = backup_dir / f"indexing_jobs_{timestamp}.json"
        shutil.copy2(OLD_INDEXING_JOBS, backup_path)
        print(f"Backup créé: {backup_path}")
    
    if OLD_QA_JOBS.exists():
        backup_path = backup_dir / f"qa_jobs_{timestamp}.json"
        shutil.copy2(OLD_QA_JOBS, backup_path)
        print(f"Backup créé: {backup_path}")
    
    print("\nMigration complète avec succès !")
    return len(normalized_jobs)


if __name__ == "__main__":
    migrated_count = migrate_jobs()
    print(f"\nNombre total de jobs migrés: {migrated_count}")
