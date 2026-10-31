"""Services pour la génération de knowledge_items sur l'ensemble des chunks
d'un document, sous forme de jobs en arrière-plan suivis via app.jobs."""
from typing import Optional, Dict

from app.jobs.manager import (
    create_job as _create_job,
    get_job as _get_job,
    get_jobs_by_type as _get_jobs_by_type,
    update_job as _update_job,
)

JOB_TYPE = "ki-generation"


def create_knowledge_generation_job(document_id: int, model: str, source: str) -> str:
    """Crée un job de génération de knowledge_items pour un document.

    Args:
        document_id: ID du document dont tous les chunks seront analysés.
        model: Modèle LLM à utiliser pour l'extraction.
        source: 'chunks' (texte des chunks) ou 'questions' (questions disponibles).

    Returns:
        job_id: L'ID unique du job créé.
    """
    job_id = _create_job(
        job_type=JOB_TYPE,
        document_categories=["validated-documents"],
        parameters={
            "document_id": document_id,
            "model_name": model,
            "source": source,
        },
        total_documents=0,
    )
    _update_job(job_id, processed_documents=0, errors=[])
    return job_id


def get_knowledge_generation_job(job_id: str) -> Optional[dict]:
    """Récupère un job par son ID."""
    return _get_job(job_id)


def get_all_knowledge_generation_jobs() -> Dict[str, dict]:
    """Récupère tous les jobs de génération de knowledge_items."""
    return {job["job_id"]: job for job in _get_jobs_by_type(JOB_TYPE)}


def get_latest_knowledge_generation_job(exclude_status: list = None) -> Optional[dict]:
    """Récupère le job le plus récent."""
    jobs = [j for j in _get_jobs_by_type(JOB_TYPE)
            if exclude_status is None or j.get("status") not in exclude_status]
    if not jobs:
        return None
    return max(jobs, key=lambda j: j.get("created_at", ""))


def update_knowledge_generation_job(
    job_id: str,
    status: str = None,
    progress: dict = None,
    processed_documents: int = None,
    total_documents: int = None,
    errors: list = None,
    error_message: str = None,
) -> bool:
    """Met à jour un job existant."""
    update_kwargs = {
        "status": status,
        "progress": progress,
        "processed_documents": processed_documents,
        "total_documents": total_documents,
        "errors": errors,
        "error_message": error_message,
    }
    return _update_job(job_id, **update_kwargs)


async def process_knowledge_generation_job(job_id: str):
    """Traite un job de génération de knowledge_items en arrière-plan.

    Parcourt tous les chunks du document ; pour chaque chunk, extrait les
    knowledge_items soit depuis le texte du chunk (source='chunks'), soit depuis
    les questions/réponses disponibles (source='questions'). La progression est
    mise à jour chunk par chunk dans le job.
    """
    job = get_knowledge_generation_job(job_id)
    if not job:
        print(f"Job {job_id} introuvable")
        return

    update_knowledge_generation_job(job_id=job_id, status="running", processed_documents=0)

    parameters = job.get("parameters", {})
    document_id = parameters.get("document_id")
    model_name = parameters.get("model_name") or "mistral-medium"
    source = parameters.get("source") or "chunks"

    errors = []
    progress = {}

    from database.database import get_db_connection, get_all_text_chunks, get_questions_by_chunk_id
    from agents.knowledge_item_agent import (
        generate_knowledge_items_from_chunk,
        generate_knowledge_items_from_questions,
        QAItemSchema,
    )

    try:
        async with await get_db_connection() as conn:
            chunks = await get_all_text_chunks(conn, document_id)
    except Exception as e:
        update_knowledge_generation_job(
            job_id=job_id, status="failed", errors=[str(e)], error_message=str(e),
        )
        return

    if not chunks:
        update_knowledge_generation_job(
            job_id=job_id, status="failed",
            errors=[f"Aucun chunk trouvé pour le document {document_id}"],
            error_message=f"Aucun chunk trouvé pour le document {document_id}",
        )
        return

    total_chunks = len(chunks)
    update_knowledge_generation_job(
        job_id=job_id, status="running", total_documents=total_chunks,
    )

    processed = 0
    for chunk in chunks:
        chunk_id = str(chunk["id"])
        text = chunk.get("content", "")

        if source == "chunks":
            if not text or not text.strip():
                progress[chunk_id] = {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "items_generated": 0,
                    "status": "empty",
                    "error": None,
                }
                processed += 1
                update_knowledge_generation_job(
                    job_id=job_id, status="running", progress=progress,
                    processed_documents=processed, errors=errors,
                )
                continue

        try:
            if source == "chunks":
                schemas = await generate_knowledge_items_from_chunk(
                    text=text,
                    chunk_id=chunk_id,
                    document_id=str(document_id),
                    page=chunk.get("num_page"),
                    position_in_page=chunk.get("position_in_page"),
                    model=model_name,
                )
            else:
                async with await get_db_connection() as conn:
                    questions = await get_questions_by_chunk_id(conn, chunk_id)
                qa_items = [
                    QAItemSchema(
                        question_id=q.get("question_id"),
                        question=q.get("content", ""),
                        answers=[a.get("content", "") for a in (q.get("answers") or [])],
                    )
                    for q in questions
                    if q.get("content") and q.get("content").strip()
                ]
                if not qa_items:
                    progress[chunk_id] = {
                        "chunk_id": chunk_id,
                        "document_id": document_id,
                        "items_generated": 0,
                        "status": "empty",
                        "error": None,
                    }
                    processed += 1
                    update_knowledge_generation_job(
                        job_id=job_id, status="running", progress=progress,
                        processed_documents=processed, errors=errors,
                    )
                    continue
                schemas = await generate_knowledge_items_from_questions(
                    qa_items=qa_items,
                    chunk_id=chunk_id,
                    document_id=str(document_id),
                    page=chunk.get("num_page"),
                    position_in_page=chunk.get("position_in_page"),
                    model=model_name,
                )

            progress[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "items_generated": len(schemas),
                "status": "completed",
                "error": None,
            }
        except Exception as e:
            print(f"Erreur lors de l'extraction des knowledge_items du chunk {chunk_id}: {e}")
            errors.append(f"Chunk {chunk_id}: {e}")
            progress[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "items_generated": 0,
                "status": "failed",
                "error": str(e),
            }

        processed += 1
        update_knowledge_generation_job(
            job_id=job_id, status="running", progress=progress,
            processed_documents=processed, errors=errors,
        )

    update_kwargs = {
        "status": "completed" if not errors else "completed_with_errors",
        "progress": progress,
        "processed_documents": processed,
        "errors": errors,
    }
    _update_job(job_id, **update_kwargs)
