"""
Services pour le job de génération des faits (affirmations) des réponses
de référence existantes, pour toutes les questions d'un document.

Complète le job de génération de questions/réponses : les réponses déjà en
base sans faits dans text_answer_facts y sont décomposées en affirmations
atomiques (essentielles/facultatives), en synchrone ou via l'API Batch
de Mistral (≈ 50% moins cher).
"""
from typing import Dict, List, Optional

from database.database import (
    get_db_connection,
    get_answers_without_facts,
    insert_answer_facts,
)
from agents import fact_extractor
from agents.token_monitor import (
    aggregate_token_usage,
    monitor_agent_call,
)
from app.jobs.manager import (
    create_job as _create_job,
    get_job as _get_job,
    get_jobs_by_type as _get_jobs_by_type,
    update_job as _update_job,
)


def create_fact_generation_job(
    document_id: Optional[int] = None,
    model_name: str = "mistral/mistral-medium",
    use_batch: bool = False,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
) -> str:
    """
    Crée un job d'extraction des faits pour toutes les réponses de référence
    d'un document (ou de tous les documents) qui n'en ont pas encore.

    Args:
        document_id: ID du document à traiter (optionnel). Si None, tous les documents.
        model_name: Modèle d'extraction au format <provider>/<model>
        use_batch: Utiliser l'API Batch de Mistral (≈ 50% moins cher)
        start_page: Première page (num_page) à traiter (optionnel)
        end_page: Dernière page (num_page) à traiter (optionnel)

    Returns:
        job_id: L'ID unique du job créé
    """
    return _create_job(
        job_type="facts-generation",
        document_categories=["validated-documents"],
        parameters={
            "document_id": document_id,
            "model_name": model_name,
            "use_batch": use_batch,
            "start_page": start_page,
            "end_page": end_page,
        },
        total_documents=0
    )


def get_fact_generation_job(job_id: str) -> Optional[dict]:
    """Récupère un job de génération de faits par son ID."""
    return _get_job(job_id)


def get_all_fact_generation_jobs() -> Dict[str, dict]:
    """Récupère tous les jobs de génération de faits."""
    jobs = _get_jobs_by_type("facts-generation")
    return {job["job_id"]: job for job in jobs}


def _update_fact_generation_job(job_id: str, **kwargs) -> bool:
    return _update_job(job_id, **kwargs)


async def _collect_answers(document_id, start_page, end_page) -> List[Dict]:
    """Réponses de référence sans faits, filtrées par plage de pages."""
    async with await get_db_connection() as conn:
        answers = await get_answers_without_facts(conn, document_id)
    if start_page is None and end_page is None:
        return answers
    return [
        answer for answer in answers
        if (start_page is None or (answer.get("num_page") or 0) >= start_page)
        and (end_page is None or (answer.get("num_page") or 0) <= end_page)
    ]


async def process_fact_generation_job(job_id: str):
    """
    Traite un job d'extraction des faits en arrière-plan : pour chaque
    réponse de référence sans faits, décompose la réponse en affirmations
    atomiques et les insère dans text_answer_facts.

    Args:
        job_id: L'ID du job à traiter
    """
    job = get_fact_generation_job(job_id)
    if not job:
        print(f"Job {job_id} introuvable")
        return

    _update_fact_generation_job(job_id, status="running", processed_documents=0)

    parameters = job.get("parameters", {})
    document_id = parameters.get("document_id")
    model_name = parameters.get("model_name") or "mistral/mistral-medium"
    use_batch = parameters.get("use_batch", False)
    start_page = parameters.get("start_page")
    end_page = parameters.get("end_page")

    provider, model = tuple(model_name.split("/"))

    answers = await _collect_answers(document_id, start_page, end_page)
    total_answers = len(answers)
    _update_fact_generation_job(job_id, total_documents=total_answers)
    print(f"{total_answers} réponse(s) sans faits à traiter...")

    errors = []
    progress = {}
    usage_records: list = []
    processed = 0
    facts_saved = 0

    def persist_progress():
        _update_fact_generation_job(
            job_id=job_id,
            status="running",
            progress=progress,
            processed_documents=processed,
            errors=errors,
            token_usage=aggregate_token_usage(usage_records),
        )

    if use_batch:
        from .batch_generation import (
            build_answer_facts_batch_requests,
            run_mistral_batch,
            parse_answer_facts_response,
            usage_records_from_batch_results,
        )

        def on_batch_poll(phase: str, info: dict):
            print(f"Batch Mistral {info.get('batch_id')}: statut {info.get('status')}")
            _update_fact_generation_job(
                job_id=job_id,
                status="running",
                progress={
                    "batch": {
                        "batch_id": info.get("batch_id"),
                        "status": info.get("status"),
                        "counts": info.get("counts"),
                        "mode": "batch"
                    }
                },
                processed_documents=processed,
                errors=errors,
            )

        try:
            requests = build_answer_facts_batch_requests(answers)
            results = await run_mistral_batch(requests, model, on_progress=on_batch_poll)
            usage_records.extend(usage_records_from_batch_results(results, model))
        except Exception as e:
            error_msg = f"Erreur API Batch: {e}"
            _update_fact_generation_job(
                job_id=job_id,
                status="failed",
                progress=progress,
                processed_documents=0,
                errors=[error_msg],
                error_message=error_msg
            )
            print(error_msg)
            return

        async with await get_db_connection() as conn:
            for answer in answers:
                answer_id = answer["answer_id"]
                result = results.get(f"facts::{answer_id}")
                error = None
                answer_facts = []
                if result is None:
                    error = "Aucun résultat retourné par le batch"
                elif result.get("error") or result.get("status") == "failed":
                    error = f"Échec de la requête batch: {result.get('error') or result.get('status')}"
                else:
                    answer_facts = parse_answer_facts_response(result.get("content", ""))
                    if not answer_facts:
                        error = "Aucun fait extrait"
                if answer_facts:
                    await insert_answer_facts(
                        answer_id, answer_facts, conn, model=model_name
                    )
                    facts_saved += len(answer_facts)
                progress[str(answer_id)] = {
                    "answer_id": answer_id,
                    "question_id": answer.get("question_id"),
                    "facts_generated": len(answer_facts),
                    "error": error,
                    "status": "completed" if not error else "failed",
                    "mode": "batch"
                }
                if error:
                    errors.append(f"answer {answer_id}: {error}")
                processed += 1
                if processed % 10 == 0 or processed == total_answers:
                    persist_progress()
    else:
        facts_agent = fact_extractor.get_answer_facts_agent(provider=provider, model=model)
        async with await get_db_connection() as conn:
            for answer in answers:
                answer_id = answer["answer_id"]
                error = None
                answer_facts = []
                try:
                    output, usage_info = monitor_agent_call(
                        facts_agent,
                        fact_extractor.FactExtractionInput(paragraph=answer["content"])
                    )
                    usage_records.append(usage_info.to_metadata())
                    answer_facts = [
                        {
                            "content": f.content,
                            "importance": f.importance if f.importance in ("essential", "optional") else "essential"
                        }
                        for f in output.facts
                    ]
                except Exception as e:
                    error = f"Erreur extraction: {e}"
                    print(error)
                if answer_facts:
                    await insert_answer_facts(
                        answer_id, answer_facts, conn, model=model_name
                    )
                    facts_saved += len(answer_facts)
                elif not error:
                    error = "Aucun fait extrait"
                progress[str(answer_id)] = {
                    "answer_id": answer_id,
                    "question_id": answer.get("question_id"),
                    "facts_generated": len(answer_facts),
                    "error": error,
                    "status": "completed" if not error else "failed"
                }
                if error:
                    errors.append(f"answer {answer_id}: {error}")
                processed += 1
                if processed % 10 == 0 or processed == total_answers:
                    persist_progress()

    final_status = "completed" if not errors else "completed_with_errors"
    _update_fact_generation_job(
        job_id=job_id,
        status=final_status,
        progress=progress,
        processed_documents=processed,
        errors=errors,
        token_usage=aggregate_token_usage(usage_records),
    )
    print(f"Job faits {job_id} terminé: {final_status} "
          f"({processed}/{total_answers} réponses, {facts_saved} faits)")
