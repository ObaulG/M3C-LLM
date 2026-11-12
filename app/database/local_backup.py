"""
Sauvegarde locale des données du projet LLMAgents (MySQL + Qdrant).

Fournit une fonction unique, `backup_local()`, appelable :
  - ponctuellement : `await backup_local()`
  - à la fermeture du serveur : branchée dans le lifespan de app/api_server.py
    (variable d'environnement LOCAL_BACKUP_ON_SHUTDOWN, défaut : activé)
  - périodiquement : `periodic_local_backup(interval)` (variable
    d'environnement LOCAL_BACKUP_INTERVAL_SECONDS, défaut : 0 = désactivé)

Ce qui est sauvegardé :
  - MySQL : uniquement les tables listées dans app/database/fix_text_encodings.py
    (TABLES, liste exhaustive du projet). Pour chaque table présente dans la
    base, le schéma (SHOW CREATE TABLE) et le contenu (INSERT INTO ...) sont
    écrits dans un fichier .sql horodaté (réutilise backup_to_sql.backup).
    Les tables absentes de la base sont ignorées avec un avertissement.
  - Qdrant : toutes les collections, sous forme de snapshots natifs (.tar.gz)
    créés via l'API REST puis téléchargés (réutilise jobs.export_data.export_qdrant).

Sortie (répertoire LOCAL_BACKUP_DIR, défaut ./backups) :
  - backup_<base>_<AAAAMMJJ_HHMMSS>.sql
  - qdrant_snapshots/<collection>_<AAAAMMJJ_HHMMSS>.tar.gz

Les fichiers de sauvegarde plus anciens que LOCAL_BACKUP_RETENTION_DAYS jours
(défaut : 30) sont supprimés à chaque exécution.

Usage en ligne de commande :
    python -m app.database.local_backup
    python -m app.database.local_backup --interval-seconds 3600
"""

import argparse
import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    from database.backup_to_sql import backup as backup_mysql
    from jobs.export_data import export_qdrant
except ImportError:
    from app.database.backup_to_sql import backup as backup_mysql
    from app.jobs.export_data import export_qdrant

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path(os.getenv("LOCAL_BACKUP_DIR", "backups"))
RETENTION_DAYS = int(os.getenv("LOCAL_BACKUP_RETENTION_DAYS", "30"))

TABLES = [
    'answers', 'chatbot_feedbacks', 'chatbot_message_chunks', 'chatbot_messages',
    'chunk_embeddings', 'document_reading_sessions', 'documents', 'entities',
    'evaluations', 'indexing_jobs', 'knowledge_item_entities', 'knowledge_item_questions',
    'knowledge_items', 'knowledge_item_themes', 'knowledge_sources', 'llm_interpretations',
    'model_evidences', 'observation_payloads', 'observations', 'observation_targets',
    'question_session_questions', 'question_sessions', 'questions',
    'session_answers', 'session_messages', 'sessions',
    'text_answer_facts', 'text_chunking_strategies', 'text_chunks',
    'text_document_chunking_validation', 'text_documents',
    'text_question_answers', 'text_question_chunks', 'text_questions', 'themes',
    'user', 'user_interests_entities', 'user_interests_themes',
    'user_knowledge_states', 'user_mistral_api_keys', 'user_model_history',
    'user_profiles', 'user_sessions']

def _cleanup_old_backups(output_dir: Path, retention_days: int = RETENTION_DAYS) -> None:
    """Supprime les sauvegardes MySQL et Qdrant plus vieilles que retention_days."""
    if retention_days <= 0:
        return
    cutoff = time.time() - retention_days * 86400

    mysql_files = output_dir.glob("backup_*.sql") if output_dir.is_dir() else []
    for f in mysql_files:
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()
            logger.info("Ancienne sauvegarde supprimée : %s", f)

    snapshots_dir = output_dir / "qdrant_snapshots"
    if snapshots_dir.is_dir():
        for f in snapshots_dir.glob("*.tar.gz"):
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                logger.info("Ancien snapshot Qdrant supprimé : %s", f)


async def backup_local(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    tables: Optional[List[str]] = None,
    include_qdrant: bool = True,
    retention_days: int = RETENTION_DAYS,
) -> dict:
    """Sauvegarde locale des tables MySQL du projet et des collections Qdrant.

    Args:
        output_dir: répertoire de destination des sauvegardes.
        tables: tables MySQL à sauvegarder (défaut : TABLES de
            fix_text_encodings.py, liste exhaustive du projet).
        include_qdrant: sauvegarder aussi les collections Qdrant.
        retention_days: suppression des sauvegardes plus vieilles que ce
            nombre de jours (0 = conservation illimitée).

    Returns:
        {"mysql": chemin du dump .sql ou None,
         "qdrant": [chemins des snapshots .tar.gz]}
    """
    if tables is None:
        tables = TABLES

    output_dir = Path(output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results: dict = {"mysql": None, "qdrant": []}

    logger.info("Sauvegarde locale démarrée (MySQL : %d tables, Qdrant : %s)",
                len(tables), "oui" if include_qdrant else "non")

    try:
        results["mysql"] = await backup_mysql(
            output_dir=output_dir, tables=list(tables)
        )
    except Exception:
        logger.exception("Échec de la sauvegarde MySQL")

    if include_qdrant:
        try:
            snapshots = await asyncio.to_thread(
                export_qdrant, output_dir, timestamp
            )
            results["qdrant"] = [str(f) for f in snapshots]
        except Exception:
            logger.exception("Échec de la sauvegarde Qdrant")

    try:
        _cleanup_old_backups(output_dir, retention_days)
    except Exception:
        logger.exception("Échec du nettoyage des anciennes sauvegardes")

    logger.info("Sauvegarde locale terminée : %s", results)
    return results


async def periodic_local_backup(interval_seconds: float) -> None:
    """Boucle de sauvegarde périodique : backup_local() toutes les
    interval_seconds. À lancer comme tâche asyncio (voir api_server.py)."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await backup_local()
        except Exception:
            logger.exception("Échec de la sauvegarde périodique")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sauvegarde locale des tables MySQL du projet et des collections Qdrant."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Répertoire de sortie (défaut : {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=0,
        help="Exécuter périodiquement toutes les N secondes (défaut : une seule fois)",
    )
    parser.add_argument(
        "--no-qdrant",
        action="store_true",
        help="Ne sauvegarder que MySQL",
    )
    args = parser.parse_args()

    if args.interval_seconds > 0:
        asyncio.run(periodic_local_backup(args.interval_seconds))
    else:
        asyncio.run(
            backup_local(
                output_dir=args.output_dir, include_qdrant=not args.no_qdrant
            )
        )


if __name__ == "__main__":
    main()
