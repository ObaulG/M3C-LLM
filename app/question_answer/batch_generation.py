"""
Génération de masse via l'API Batch de Mistral (https://docs.mistral.ai/api/#tag/Batch).

L'API Batch facture les requêtes environ 50% moins cher que l'API temps réel,
en échange d'un délai de traitement pouvant aller jusqu'à 24h. Ce module
construit les requêtes JSONL (une par chunk ou par réponse), les soumet en
batch, suit leur progression puis récupère et parse les résultats.

Les prompts système sont réutilisés depuis les YAML de agents/prompts afin de
produire des sorties identiques au mode synchrone (agents atomic_agents).
"""
import asyncio
import json
import os
import re
import tempfile
from typing import Any, Callable, Dict, List, Optional

from agents import qa_single_agent
from agents import fact_extractor
from mistralai import Mistral

POLL_INTERVAL_SECONDS = 60

_TERMINAL_STATUSES = {"SUCCESS", "FAILED", "PARTIALLY_SUCCEEDED", "TIME_EXCEEDED", "TIMEOUT_EXCEEDED", "EXPIRED", "CANCELLED"}


def _create_mistral_batch(client: Mistral, file_id: str, model: str):
    """Crée un batch, en gérant les deux générations du SDK mistralai :
    >= 1.12 expose client.batches.create(input_file_id=..., completion_window=...),
    les versions antérieures exposent client.batch.jobs.create(input_files=..., endpoint=...).
    """
    batches_api = getattr(client, "batches", None)
    if batches_api is not None and hasattr(batches_api, "create"):
        return batches_api.create(
            input_file_id=file_id,
            model=model,
            completion_window="24h",
        )
    return client.batch.jobs.create(
        input_files=[file_id],
        endpoint="/v1/chat/completions",
        model=model,
    )


def _retrieve_mistral_batch(client: Mistral, batch_id: str):
    """Récupère un batch par son ID, selon la génération du SDK mistralai."""
    batches_api = getattr(client, "batches", None)
    if batches_api is not None and hasattr(batches_api, "retrieve"):
        return batches_api.retrieve(batch_id)
    return client.batch.jobs.get(job_id=batch_id)


def _batch_request_counts(batch) -> Optional[dict]:
    """Extrait un résumé de l'avancement du batch, quel que soit le SDK."""
    counts = getattr(batch, "request_counts", None)
    if counts is not None:
        return counts
    return {
        "total": getattr(batch, "total_requests", 0),
        "completed": getattr(batch, "completed_requests", 0),
        "succeeded": getattr(batch, "succeeded_requests", 0),
        "failed": getattr(batch, "failed_requests", 0),
    }


def _get_raw_mistral_client() -> Mistral:
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("La variable d'environnement MISTRAL_API_KEY n'est pas définie.")
    return Mistral(api_key=api_key)


def qa_system_prompt(user_prompt: Optional[str] = None) -> str:
    """Construit le message système pour la génération de questions/réponses."""
    system_prompt = qa_single_agent.system_prompt_generator.generate_prompt()
    system_prompt += (
        '\nSchéma JSON exact attendu : {"QA_list": [{"question": "str", "answer": "str"}]}\n'
    )
    if user_prompt:
        system_prompt += f"\nInstructions supplémentaires de l'utilisateur :\n{user_prompt}\n"
    return system_prompt


def qa_user_message(chunk_content: str, num_questions: int, user_prompt: Optional[str] = None) -> str:
    """Construit le message utilisateur, au même format que l'entrée de l'agent QA synchrone."""
    return json.dumps(
        {
            "message": user_prompt or "",
            "document": chunk_content,
            "num_questions": num_questions,
        },
        ensure_ascii=False,
    )


def answer_facts_system_prompt() -> str:
    """Construit le message système pour l'extraction des faits d'une réponse."""
    return fact_extractor._answer_facts_prompt.generate_prompt() + (
        '\nSchéma JSON exact attendu : {"facts": [{"content": "str", '
        '"importance": "essential"|"optional"}]}\n'
    )


def build_qa_batch_requests(
    chunks: List[Dict],
    num_questions: int,
    user_prompt: Optional[str] = None,
) -> List[Dict]:
    """Construit une requête batch par chunk (body au format de l'API Batch de Mistral)."""
    requests = []
    for chunk in chunks:
        chunk_id = str(chunk.get("id"))
        requests.append({
            "custom_id": f"qa::{chunk_id}",
            "params": {
                "messages": [
                    {"role": "system", "content": qa_system_prompt(user_prompt)},
                    {"role": "user", "content": qa_user_message(
                        chunk.get("content", ""), num_questions, user_prompt)},
                ],
                "temperature": 0.7,
            },
        })
    return requests


def build_answer_facts_batch_requests(answers: List[Dict]) -> List[Dict]:
    """Construit une requête batch par réponse de référence (answer_id + contenu)."""
    requests = []
    for answer in answers:
        requests.append({
            "custom_id": f"facts::{answer['answer_id']}",
            "params": {
                "messages": [
                    {"role": "system", "content": answer_facts_system_prompt()},
                    {"role": "user", "content": json.dumps(
                        {"paragraph": answer["content"]}, ensure_ascii=False)},
                ],
                "temperature": 0.1,
            },
        })
    return requests


def extract_json_object(text: str) -> Optional[dict]:
    """Extrait le premier objet JSON valide d'une réponse texte du modèle."""
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except ValueError:
            return None
    return None


def parse_qa_response(raw_content: str) -> List[Dict]:
    """Parse la réponse d'une requête batch de génération de questions/réponses."""
    data = extract_json_object(raw_content or "")
    if not data or not isinstance(data.get("QA_list"), list):
        return []
    qa_list = []
    for item in data["QA_list"]:
        question = (item.get("question") or "").strip()
        answer = (item.get("answer") or "").strip()
        if question and answer:
            qa_list.append({"question": question, "answer": answer})
    return qa_list


def parse_answer_facts_response(raw_content: str) -> List[Dict]:
    """Parse la réponse d'une requête batch d'extraction de faits."""
    data = extract_json_object(raw_content or "")
    if not data or not isinstance(data.get("facts"), list):
        return []
    facts = []
    for item in data["facts"]:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        importance = item.get("importance")
        if importance not in ("essential", "optional"):
            importance = "essential"
        facts.append({"content": content, "importance": importance})
    return facts


async def run_mistral_batch(
    requests: List[Dict],
    model: str,
    on_progress: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Dict[str, Dict]:
    """
    Soumet une liste de requêtes à l'API Batch de Mistral et attend la fin du traitement.

    Args:
        requests: Liste de requêtes au format {"custom_id": ..., "params": {...}}
        model: Nom du modèle Mistral (sans préfixe de provider)
        on_progress: Callback optionnel (phase, infos_batch) appelé à chaque sondage

    Returns:
        Dictionnaire custom_id -> {"status": ..., "content": ..., "error": ...}
    """
    if not requests:
        return {}

    client = _get_raw_mistral_client()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as tmp:
        for request in requests:
            tmp.write(json.dumps({
                "custom_id": request["custom_id"],
                "body": {
                    "model": model,
                    "messages": request["params"]["messages"],
                    "temperature": request["params"].get("temperature", 0.7),
                },
            }, ensure_ascii=False) + "\n")
        input_path = tmp.name

    with open(input_path, "rb") as input_file:
        uploaded = client.files.upload(
            file={
                "file_name": os.path.basename(input_path),
                "content": input_file,
                "content_type": "application/jsonl",
            },
            purpose="batch",
        )

    batch = _create_mistral_batch(client, uploaded.id, model)

    print(f"Batch Mistral créé: {batch.id} ({len(requests)} requêtes, modèle {model})")

    while True:
        batch = _retrieve_mistral_batch(client, batch.id)
        if on_progress:
            on_progress("polling", {
                "batch_id": batch.id,
                "status": str(getattr(batch, "status", "")),
                "counts": _batch_request_counts(batch),
            })
        if str(getattr(batch, "status", "")) in _TERMINAL_STATUSES:
            break
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

    results: Dict[str, Dict] = {}
    status = str(getattr(batch, "status", ""))

    if status in ("SUCCESS", "PARTIALLY_SUCCEEDED"):
        output_file_id = getattr(batch, "output_file_id", getattr(batch, "output_file", None))
        error_file_id = getattr(batch, "error_file_id", getattr(batch, "error_file", None))
        if not isinstance(output_file_id, str):
            output_file_id = None
        if not isinstance(error_file_id, str):
            error_file_id = None
        if output_file_id:
            content = client.files.download(file_id=output_file_id)
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            for line in content.splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                custom_id = entry.get("custom_id") or entry.get("request_id")
                body = entry.get("body") or {}
                choices = body.get("choices") or []
                message_content = ""
                if choices:
                    message_content = (choices[0].get("message") or {}).get("content") or ""
                usage = body.get("usage") or {}
                results[custom_id] = {
                    "status": entry.get("status", "success"),
                    "content": message_content,
                    "error": None,
                    "usage": {
                        "input_tokens": usage.get("prompt_tokens", 0) or 0,
                        "cached_tokens": (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0,
                        "output_tokens": usage.get("completion_tokens", 0) or 0,
                    },
                }
        if error_file_id:
            error_content = client.files.download(file_id=error_file_id)
            if isinstance(error_content, bytes):
                error_content = error_content.decode("utf-8")
            for line in error_content.splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                custom_id = entry.get("custom_id") or entry.get("request_id")
                results[custom_id] = {
                    "status": "failed",
                    "content": "",
                    "error": json.dumps(entry.get("error", entry), ensure_ascii=False),
                }
    else:
        raise RuntimeError(f"Le batch Mistral {batch.id} s'est terminé avec le statut {status}.")

    return results


def usage_records_from_batch_results(results: Dict[str, Dict], model: str) -> List[Dict]:
    """Convertit les résultats d'un batch en métadonnées de consommation
    (une par requête réussie), avec le coût calculé au tarif Batch API
    (remise de 50 %), pour agrégation via aggregate_token_usage."""
    try:
        from pricing import compute_cost_eur
    except ImportError:
        from app.pricing import compute_cost_eur

    records = []
    for result in results.values():
        usage = result.get("usage") or {}
        input_tokens = usage.get("input_tokens", 0) or 0
        cached_tokens = usage.get("cached_tokens", 0) or 0
        output_tokens = usage.get("output_tokens", 0) or 0
        record = {
            "input_tokens": input_tokens,
            "cached_tokens": cached_tokens,
            "output_tokens": output_tokens,
        }
        cost_detail = compute_cost_eur(
            model,
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
            batch_api=True,
        )
        if cost_detail is not None:
            record["cost_eur"] = cost_detail["total_eur"]
            record["cost_detail"] = cost_detail
        records.append(record)
    return records
