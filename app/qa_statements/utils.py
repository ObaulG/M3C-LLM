"""Utilitaires communs au prototype qa_statements."""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import instructor

from app.agents.instructor_factory import create_client

DIR_PATH = Path(__file__).parent
JSON_PATH = DIR_PATH / "qa_statements.json"
RESULTS_DIR = DIR_PATH / "results"

FALLBACK_MODEL = "mistral-medium"


def get_llm_client(provider: str, model: Optional[str], async_mode: bool = False):
    """Retourne un client LLM (instructor) selon le fournisseur demandé."""
    if model is None:
        model = FALLBACK_MODEL
    return create_client(
        provider=provider,
        model=model,
        async_mode=async_mode,
        instructor_mode=instructor.Mode.JSON,
    )


def load_json(path: Path = JSON_PATH) -> Dict:
    """Charge le JSON de données qa_statements.json."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Dict, path: Path = JSON_PATH) -> None:
    """Écrit le JSON de données qa_statements.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def init_json(data_model: Optional[str] = None) -> Dict:
    """Retourne la structure vierge (ou existante) du JSON de données."""
    if JSON_PATH.exists():
        data = load_json()
    else:
        data = {"metadata": {}, "documents": {}}
    if data_model:
        now = datetime.now().isoformat(timespec="seconds")
        data["metadata"]["updated_at"] = now
        data["metadata"]["statement_extraction_model"] = data_model
        if "created_at" not in data["metadata"]:
            data["metadata"]["created_at"] = now
    return data


def pick_n_questions(questions: List[Dict], n: int, seed: Optional[int] = None) -> List[Dict]:
    """Tire au hasard n questions dans une liste, sans remise.

    Si la liste contient moins de n questions, toutes sont retournées.
    """
    if n <= 0:
        return []
    if n >= len(questions):
        return list(questions)
    if seed is not None:
        random.Random(seed).shuffle(questions)
        return questions[:n]
    return random.sample(questions, n)


def all_questions_flat(data: Dict) -> List[Dict]:
    """Aplatit le JSON en une liste de questions (document_id ajouté à chaque entrée)."""
    flat = []
    for document_id, document in data.get("documents", {}).items():
        for question in document.get("questions", []):
            entry = dict(question)
            entry["document_id"] = document_id
            flat.append(entry)
    return flat


def timestamped_filename(prefix: str, extension: str) -> str:
    """Construit un nom de fichier horodaté pour les résultats."""
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{now}.{extension}"
