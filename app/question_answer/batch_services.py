"""
Génération de questions via l'API Batch de Mistral (https://docs.mistral.ai/api/#tag/Batch).

Le mode batch permet de soumettre en une seule requête la génération de questions
pour un grand nombre de chunks : les requêtes sont regroupées dans un fichier JSONL,
envoyées à l'API Batch de Mistral, puis les résultats sont récupérés une fois le
job terminé. Utile pour les travaux massifs, avec une facturation réduite.

Flux :
1. Construction d'une requête chat par chunk (même prompt que l'agent qa_single).
2. Téléversement du fichier JSONL (purpose="batch").
3. Création d'un job batch côté Mistral.
4. Polling du job jusqu'à SUCCESS / PARTIAL_SUCCESS / FAILED.
5. Téléchargement du fichier de résultats et parsing des Q/R par chunk.
"""
import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx

from agents.prompt_loader import get_prompt

MISTRAL_API_BASE_URL = os.getenv("MISTRAL_API_BASE_URL", "https://api.mistral.com/v1")
BATCH_POLL_INTERVAL_SECONDS = int(os.getenv("MISTRAL_BATCH_POLL_INTERVAL", "30"))
BATCH_TERMINAL_STATUSES = {"SUCCESS", "PARTIAL_SUCCESS", "FAILED", "CANCELLED", "TIMEOUT"}
BATCH_ERROR_STATUSES = {"FAILED", "CANCELLED", "TIMEOUT"}


def _get_mistral_api_key() -> str:
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError(
            "La clé API Mistral n'est pas définie. "
            "Configurez la variable d'environnement MISTRAL_API_KEY pour utiliser le mode batch."
        )
    return api_key


def _get_qa_system_prompt() -> str:
    """
    Retourne le prompt système de l'agent qa_single (même prompt que la génération standard),
    pour garantir des résultats cohérents entre les deux modes.
    """
    try:
        return get_prompt("qa_single", "default").generate_prompt()
    except Exception as e:
        raise ValueError(f"Impossible de charger le prompt qa_single: {e}")


def build_batch_request_line(
    custom_id: str,
    chunk_content: str,
    num_questions: int,
    model: str,
    user_prompt: Optional[str] = None,
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """
    Construit une ligne du fichier JSONL envoyé à l'API Batch.

    Le body est une requête chat standard (mêmes messages que l'agent qa_single),
    avec response_format json_object pour obtenir un JSON {"QA_list": [...]}.
    """
    user_content = json.dumps({
        "message": user_prompt or "",
        "document": chunk_content,
        "num_questions": num_questions,
    }, ensure_ascii=False)

    return {
        "custom_id": custom_id,
        "body": {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": _get_qa_system_prompt()},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
        },
    }


async def upload_batch_file(request_lines: List[Dict[str, Any]]) -> str:
    """
    Téléverse le fichier JSONL des requêtes vers l'API Mistral (purpose="batch").

    Returns:
        L'ID du fichier téléversé.
    """
    payload = "\n".join(json.dumps(line, ensure_ascii=False) for line in request_lines).encode("utf-8")
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{MISTRAL_API_BASE_URL}/files",
            headers={"Authorization": f"Bearer {_get_mistral_api_key()}"},
            data={"purpose": "batch"},
            files={"file": ("batch_requests.jsonl", payload, "application/json")},
        )
        if response.status_code not in (200, 201):
            raise RuntimeError(f"Échec du téléversement du fichier batch ({response.status_code}): {response.text}")
        return response.json()["id"]


async def create_batch_job(file_id: str, model: str) -> str:
    """
    Crée un job batch côté Mistral à partir du fichier de requêtes.

    Returns:
        L'ID du job batch Mistral.
    """
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{MISTRAL_API_BASE_URL}/batch/jobs",
            headers={"Authorization": f"Bearer {_get_mistral_api_key()}"},
            json={"model": model, "input_files": [file_id]},
        )
        if response.status_code not in (200, 201):
            raise RuntimeError(f"Échec de la création du job batch ({response.status_code}): {response.text}")
        return response.json()["id"]


async def wait_for_batch_job(
    batch_job_id: str,
    on_status: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Attend la fin d'un job batch Mistral en le pollant périodiquement.

    Args:
        batch_job_id: ID du job batch Mistral
        on_status: callback async optionnel (status, job_dict) appelé à chaque poll

    Returns:
        Le dict final du job batch (contient notamment output_file_id et status)
    """
    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            response = await client.get(
                f"{MISTRAL_API_BASE_URL}/batch/jobs/{batch_job_id}",
                headers={"Authorization": f"Bearer {_get_mistral_api_key()}"},
            )
            if response.status_code != 200:
                raise RuntimeError(f"Échec du polling du job batch {batch_job_id} ({response.status_code}): {response.text}")
            job = response.json()
            status = job.get("status", "UNKNOWN")
            if on_status:
                try:
                    await on_status(status, job)
                except Exception:
                    pass
            if status in BATCH_TERMINAL_STATUSES:
                return job
            await asyncio.sleep(BATCH_POLL_INTERVAL_SECONDS)


async def download_batch_results(output_file_id: str) -> List[Dict[str, Any]]:
    """
    Télécharge le fichier de résultats d'un job batch et retourne les lignes parsées.

    Returns:
        Liste de dicts avec les clés custom_id et response (réponse chat brute par requête)
    """
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.get(
            f"{MISTRAL_API_BASE_URL}/files/{output_file_id}/content",
            headers={"Authorization": f"Bearer {_get_mistral_api_key()}"},
        )
        if response.status_code != 200:
            raise RuntimeError(f"Échec du téléchargement des résultats batch ({response.status_code}): {response.text}")
        return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def parse_batch_result_line(result_line: Dict[str, Any]) -> Tuple[str, Optional[List[Dict[str, str]]], Optional[str]]:
    """
    Extrait les Q/R d'une ligne de résultat batch.

    Returns:
        Tuple (custom_id, liste de {"question", "answer"} ou None, message d'erreur ou None)
    """
    custom_id = result_line.get("custom_id", "")
    response = result_line.get("response") or {}
    if response.get("status_code") and response.get("status_code") >= 400:
        return custom_id, None, f"Erreur API ({response.get('status_code')})"
    body = response.get("body") or {}
    choices = body.get("choices") or []
    if not choices:
        error = (body.get("message") or {}).get("error") or (body.get("error") or {})
        return custom_id, None, f"Pas de réponse du modèle: {error or 'réponse vide'}"
    content = choices[0].get("message", {}).get("content", "")
    try:
        parsed = json.loads(content)
        qa_list = parsed.get("QA_list") if isinstance(parsed, dict) else parsed
        if not qa_list or not isinstance(qa_list, list):
            return custom_id, None, "Format de réponse inattendu (QA_list absent ou vide)"
        pairs = []
        for qa in qa_list:
            question = (qa.get("question") or "").strip()
            answer = (qa.get("answer") or "").strip()
            if question and answer:
                pairs.append({"question": question, "answer": answer})
        if not pairs:
            return custom_id, None, "Aucune paire question/réponse valide dans la réponse"
        return custom_id, pairs, None
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        return custom_id, None, f"Réponse non parsable en JSON: {e}"


async def run_batch_generation(
    request_lines: List[Dict[str, Any]],
    model: str,
    on_status: Optional[Any] = None,
) -> Tuple[Dict[str, List[Dict[str, str]]], List[str]]:
    """
    Exécute le cycle complet de génération batch : upload, création du job, polling, résultats.

    Args:
        request_lines: lignes de requêtes (une par chunk), cf. build_batch_request_line
        model: nom du modèle Mistral à utiliser
        on_status: callback async optionnel (status, job_dict) appelé à chaque poll

    Returns:
        Tuple (custom_id -> liste de {"question", "answer"}, liste d'erreurs globales)
    """
    file_id = await upload_batch_file(request_lines)
    print(f"[batch] Fichier de requêtes téléversé: {file_id} ({len(request_lines)} requêtes)")
    batch_job_id = await create_batch_job(file_id, model)
    print(f"[batch] Job batch Mistral créé: {batch_job_id}")

    job = await wait_for_batch_job(batch_job_id, on_status=on_status)
    status = job.get("status")
    print(f"[batch] Job batch {batch_job_id} terminé avec le statut: {status}")

    if status in BATCH_ERROR_STATUSES or not job.get("output_file_id"):
        errors = [f"Job batch Mistral terminé avec le statut {status}"]
        if job.get("errors"):
            errors.append(f"Détails: {job.get('errors')}")
        return {}, errors

    result_lines = await download_batch_results(job["output_file_id"])
    print(f"[batch] {len(result_lines)} résultats récupérés")

    results: Dict[str, List[Dict[str, str]]] = {}
    errors: List[str] = []
    for line in result_lines:
        custom_id, pairs, error = parse_batch_result_line(line)
        if error:
            errors.append(f"chunk {custom_id}: {error}")
        elif pairs:
            results[custom_id] = pairs
    if status == "PARTIAL_SUCCESS":
        errors.append(f"Job batch partiellement réussi: {len(results)}/{len(request_lines)} requêtes valides")
    return results, errors
