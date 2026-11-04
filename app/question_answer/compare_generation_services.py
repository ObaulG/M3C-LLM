"""Services pour la génération comparative multi-modèles (réservée admins/experts).

Pour chaque chunk sélectionné et chaque modèle choisi, génère :
- des paires question/réponse (agent qa_single),
- les faits (affirmations) de chaque réponse (agent fact_extractor),
- les éléments de connaissance/compétence du chunk (agent knowledge_element_extractor).

Les résultats ne sont JAMAIS écrits en base de données : ils sont conservés
uniquement en mémoire (dict `_compare_results`), et le job ne persiste que
des informations de progression (statut, chunks traités, erreurs).
"""
import time
from typing import Any, Dict, List, Optional, Tuple

import database
from database.database import get_db_connection
from app.jobs.manager import (
    create_job as _create_job,
    get_job as _get_job,
    update_job as _update_job,
)
from question_answer.generation_services import generate_questions_single_answer_for_chunk
from agents.fact_extractor import get_answer_facts_agent, FactExtractionInput
from agents.knowledge_element_extractor import extract_knowledge_elements

COMPARE_JOB_TYPE = "qa-compare-generation"

# Résultats en mémoire uniquement : job_id -> résultat complet
_compare_results: Dict[str, dict] = {}


def _split_model_name(model_name: str) -> Tuple[str, str]:
    """Sépare un nom de modèle au format <provider>/<model> (défaut : mistral)."""
    if "/" in model_name:
        provider, model = model_name.split("/", 1)
        return provider, model
    return "mistral", model_name


def create_compare_generation_job(
    chunk_ids: List[str],
    models: List[str],
    num_questions: int = 3,
    user_prompt: Optional[str] = None,
) -> str:
    """Crée un job de génération comparative (métadonnées seules, résultats en mémoire)."""
    job_id = _create_job(
        job_type=COMPARE_JOB_TYPE,
        document_categories=["compare-generation"],
        parameters={
            "chunk_ids": chunk_ids,
            "models": models,
            "num_questions_per_chunk": num_questions,
            "user_prompt": user_prompt,
        },
        total_documents=len(chunk_ids),
    )
    _update_job(job_id, progress={}, processed_documents=0)
    return job_id


def get_compare_generation_job(job_id: str) -> Optional[dict]:
    """Retourne le job avec les résultats en mémoire associés (le cas échéant)."""
    job = _get_job(job_id)
    if not job:
        return None
    job = dict(job)
    job["results"] = _compare_results.get(job_id)
    return job


async def _generate_answer_facts(
    answer_text: str, provider: str, model: str, usage_sink: Optional[list] = None
) -> List[dict]:
    """Extrait les faits d'une réponse avec l'agent fact_extractor (aucune sauvegarde)."""
    from agents.token_monitor import monitor_agent_call

    agent = get_answer_facts_agent(provider=provider, model=model)
    output, usage_info = monitor_agent_call(agent, FactExtractionInput(paragraph=answer_text))
    if usage_sink is not None:
        usage_sink.append(usage_info.to_metadata())
    return [
        {
            "content": f.content,
            "importance": f.importance if f.importance in ("essential", "optional") else "essential",
        }
        for f in output.facts
    ]


async def _generate_knowledge_elements(
    chunk: dict, model: str, usage_sink: Optional[list] = None
) -> List[dict]:
    """Extrait les éléments de connaissance du chunk (aucune sauvegarde)."""
    candidates = await extract_knowledge_elements(
        text=chunk.get("content", ""),
        chunk_id=str(chunk.get("id", "")),
        document_id=str(chunk.get("document_id", "")),
        page=chunk.get("num_page"),
        position_in_page=chunk.get("position_in_page"),
        model=model,
        usage_sink=usage_sink,
    )
    return [c.to_dict() for c in candidates]


def _aggregate_token_usage(usage_records: List[dict]) -> Dict[str, Any]:
    """Agrège une liste de métadonnées de consommation en un total consolidé."""
    totals: Dict[str, Any] = {
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 0,
        "cost_eur": 0.0,
        "cost_available": False,
    }
    for record in usage_records:
        totals["calls"] += 1
        totals["input_tokens"] += record.get("input_tokens", 0)
        totals["output_tokens"] += record.get("output_tokens", 0)
        totals["cached_tokens"] += record.get("cached_tokens", 0)
        if record.get("cost_eur") is not None:
            totals["cost_eur"] += record["cost_eur"]
            totals["cost_available"] = True
    totals["total_tokens"] = totals["input_tokens"] + totals["output_tokens"]
    totals["cost_eur"] = round(totals["cost_eur"], 6)
    if not totals["cost_available"]:
        totals["cost_eur"] = None
    return totals


async def process_compare_generation_job(job_id: str):
    """
    Traite un job de génération comparative : pour chaque chunk, pour chaque
    modèle, génère questions/réponses puis faits, ainsi que les éléments de
    connaissance. Aucune donnée n'est sauvegardée en base de données.
    """
    job = _get_job(job_id)
    if not job:
        print(f"Job de comparaison {job_id} introuvable")
        return

    parameters = job.get("parameters", {})
    chunk_ids = parameters.get("chunk_ids", [])
    models = parameters.get("models", [])
    num_questions = parameters.get("num_questions_per_chunk", 3)
    user_prompt = parameters.get("user_prompt")

    _update_job(job_id, status="running", processed_documents=0)

    results: Dict[str, Any] = {
        "job_id": job_id,
        "parameters": parameters,
        "chunks": [],
    }
    errors: List[str] = []
    processed = 0
    progress = job.get("progress", {})

    for chunk_id in chunk_ids:
        chunk_entry: Dict[str, Any] = {
            "chunk_id": chunk_id,
            "document_id": None,
            "num_page": None,
            "models": [],
            "error": None,
        }
        try:
            async with await get_db_connection() as conn:
                chunk = await database.get_chunk_by_id(conn, chunk_id)

            if not chunk:
                raise ValueError(f"Chunk {chunk_id} introuvable")

            chunk_entry["document_id"] = chunk.get("document_id")
            chunk_entry["num_page"] = chunk.get("num_page")

            for model_name in models:
                provider, model = _split_model_name(model_name)
                start_time = time.time()
                model_entry: Dict[str, Any] = {
                    "model": model_name,
                    "qa": [],
                    "knowledge_elements": [],
                    "error": None,
                }
                model_usage_records: List[dict] = []
                try:
                    qa_list, error = await generate_questions_single_answer_for_chunk(
                        chunk_content=chunk.get("content", ""),
                        chunk_id=str(chunk_id),
                        document_id=str(chunk.get("document_id", "")),
                        num_questions=num_questions,
                        model_name=f"{provider}/{model}",
                        user_prompt=user_prompt,
                        usage_sink=model_usage_records,
                    )

                    if qa_list is not None and getattr(qa_list, "QA_list", None):
                        for qa in qa_list.QA_list:
                            qa_entry = {"question": qa.question, "answer": qa.answer, "facts": []}
                            try:
                                qa_entry["facts"] = await _generate_answer_facts(
                                    qa.answer, provider, model, usage_sink=model_usage_records
                                )
                            except Exception as e:
                                qa_entry["facts_error"] = str(e)
                            model_entry["qa"].append(qa_entry)
                    elif not error:
                        error = "Aucune question générée par le modèle"

                    if error:
                        model_entry["error"] = error
                        errors.append(f"chunk {chunk_id} / modèle {model_name}: {error}")

                    try:
                        model_entry["knowledge_elements"] = await _generate_knowledge_elements(
                            chunk, model, usage_sink=model_usage_records
                        )
                    except Exception as e:
                        model_entry["knowledge_elements_error"] = str(e)
                        errors.append(
                            f"chunk {chunk_id} / modèle {model_name} (éléments de connaissance): {e}"
                        )

                except Exception as e:
                    model_entry["error"] = str(e)
                    errors.append(f"chunk {chunk_id} / modèle {model_name}: {e}")

                model_entry["generation_time"] = round(time.time() - start_time, 2)
                model_entry["token_usage"] = _aggregate_token_usage(model_usage_records)
                chunk_entry["models"].append(model_entry)

                progress[str(chunk_id)] = {
                    "chunk_id": chunk_id,
                    "document_id": chunk_entry["document_id"],
                    "status": "running",
                }
                _update_job(
                    job_id=job_id,
                    status="running",
                    progress=progress,
                    processed_documents=processed,
                    errors=errors,
                )

        except Exception as e:
            chunk_entry["error"] = str(e)
            errors.append(f"chunk {chunk_id}: {e}")

        results["chunks"].append(chunk_entry)
        _compare_results[job_id] = results
        processed += 1
        progress[str(chunk_id)] = {
            "chunk_id": chunk_id,
            "document_id": chunk_entry["document_id"],
            "status": "completed" if not chunk_entry["error"] else "failed",
        }
        _update_job(
            job_id=job_id,
            status="running",
            progress=progress,
            processed_documents=processed,
            errors=errors,
        )

    job_usage: Dict[str, Any] = {
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 0,
        "cost_eur": 0.0,
        "cost_available": False,
    }
    for chunk_entry in results["chunks"]:
        for model_entry in chunk_entry.get("models", []):
            usage = model_entry.get("token_usage") or {}
            job_usage["calls"] += usage.get("calls", 0)
            job_usage["input_tokens"] += usage.get("input_tokens", 0)
            job_usage["output_tokens"] += usage.get("output_tokens", 0)
            job_usage["cached_tokens"] += usage.get("cached_tokens", 0)
            if usage.get("cost_eur") is not None:
                job_usage["cost_eur"] += usage["cost_eur"]
                job_usage["cost_available"] = True
    job_usage["total_tokens"] = job_usage["input_tokens"] + job_usage["output_tokens"]
    job_usage["cost_eur"] = round(job_usage["cost_eur"], 6) if job_usage["cost_available"] else None
    results["token_usage"] = job_usage

    final_status = "completed" if not errors else "completed_with_errors"
    _update_job(job_id, status=final_status, processed_documents=processed, errors=errors)
    print(f"Job de comparaison {job_id} terminé: {final_status} ({processed}/{len(chunk_ids)} chunks)")
