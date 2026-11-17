"""
Module pour le logging Excel des évaluations de qualité des questions.

Permet d'enregistrer, pour chaque question évaluée via la fenêtre modale
d'évaluation de qualité :
- le texte de la question, le texte du chunk et la réponse générée,
- les scores (1 à 3) des critères :
  * Question : Fluidité, Clarté, Concision
  * Réponse générée : Pertinence, Fidélité au passage, Adéquation du corrigé

Les lignes sont ajoutées au fichier question_quality_evaluations.xlsx,
créé avec ses en-têtes lors de la première sauvegarde.
"""

from datetime import datetime
from pathlib import Path
from threading import Lock

from openpyxl import Workbook, load_workbook

XLSX_PATH = "question_quality_evaluations.xlsx"

XLSX_HEADERS = [
    "timestamp",
    "question_id",
    "document_id",
    "chunk_id",
    "num_page",
    "question_text",
    "chunk_text",
    "generated_answer",
    "fluidite",
    "clarte",
    "concision",
    "pertinence",
    "fidelite_au_passage",
    "adequation_du_corrige",
    "commentaire",
]

_write_lock = Lock()


def _ensure_workbook(path: str) -> None:
    """Crée le fichier Excel avec ses en-têtes s'il n'existe pas."""
    if Path(path).exists():
        return
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "evaluations_qualite"
    sheet.append(XLSX_HEADERS)
    workbook.save(path)


def log_quality_evaluation_to_xlsx(evaluation: dict) -> str:
    """
    Ajoute une ligne d'évaluation de qualité au fichier Excel.

    Args:
        evaluation: Dictionnaire contenant les métadonnées de la question,
            les textes (question, chunk, réponse générée), les scores des
            six critères (1 à 3) et un commentaire optionnel.

    Returns:
        Le chemin du fichier Excel écrit.
    """
    row = [
        evaluation.get("timestamp") or datetime.now().isoformat(),
        evaluation.get("question_id"),
        evaluation.get("document_id"),
        evaluation.get("chunk_id"),
        evaluation.get("num_page"),
        evaluation.get("question_text"),
        evaluation.get("chunk_text"),
        evaluation.get("generated_answer"),
        evaluation.get("fluidite"),
        evaluation.get("clarte"),
        evaluation.get("concision"),
        evaluation.get("pertinence"),
        evaluation.get("fidelite_au_passage"),
        evaluation.get("adequation_du_corrige"),
        evaluation.get("commentaire", ""),
    ]

    with _write_lock:
        _ensure_workbook(XLSX_PATH)
        workbook = load_workbook(XLSX_PATH)
        sheet = workbook.active
        sheet.append(row)
        workbook.save(XLSX_PATH)

    return XLSX_PATH
