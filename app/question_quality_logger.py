"""
Module pour le logging CSV des évaluations de qualité des questions.

Permet d'enregistrer, pour chaque question évaluée via la fenêtre modale
d'évaluation de qualité :
- le texte de la question, le texte du chunk et la réponse générée,
- les scores (1 à 3) des critères :
  * Question : Fluidité, Clarté, Concision
  * Réponse générée : Pertinence, Fidélité au passage, Adéquation du corrigé

Les lignes sont ajoutées au fichier question_quality_evaluations.csv,
créé avec ses en-têtes lors de la première sauvegarde.
"""

import csv
import os
from datetime import datetime
from threading import Lock

CSV_PATH = "question_quality_evaluations.csv"

CSV_HEADERS = [
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


def log_quality_evaluation_to_csv(evaluation: dict) -> str:
    """
    Ajoute une ligne d'évaluation de qualité au fichier CSV.

    Args:
        evaluation: Dictionnaire contenant les métadonnées de la question,
            les textes (question, chunk, réponse générée), les scores des
            six critères (1 à 3) et un commentaire optionnel.

    Returns:
        Le chemin du fichier CSV écrit.
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
        file_exists = os.path.exists(CSV_PATH)
        with open(CSV_PATH, "a", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.writer(csvfile)
            if not file_exists:
                writer.writerow(CSV_HEADERS)
            writer.writerow(row)

    return CSV_PATH
