# session_csv_logger.py
"""
Module pour le logging CSV des réponses utilisateur dans les sessions de questions.

Ce module permet d'enregistrer automatiquement, à chaque soumission de réponse,
les données nécessaires pour une évaluation humaine ultérieure :
- ID et texte de la question
- Réponse de l'utilisateur
- Note, commentaire et modèle de l'évaluateur

Un fichier CSV est créé par session dans le dossier session_evaluations/.
"""

import csv
import os
from pathlib import Path

CSV_DIR = "session_evaluations"

CSV_HEADERS = [
    "timestamp",
    "session_id",
    "question_id",
    "question_text",
    "user_answer",
    "score",
    "feedback",
    "model",
    "message_type",
    "evaluation_type"
]


def ensure_csv_dir():
    """Crée le dossier de logging s'il n'existe pas."""
    Path(CSV_DIR).mkdir(parents=True, exist_ok=True)


def get_session_csv_path(session_id: str) -> str:
    """Retourne le chemin du CSV pour une session donnée."""
    return os.path.join(CSV_DIR, f"session_{session_id}.csv")


def log_response_to_csv(session_id: str, user_response) -> None:
    """
    Ajoute une ou plusieurs lignes au CSV de la session (une par évaluation).
    Crée le fichier avec les headers si c'est le premier appel pour cette session.

    Args:
        session_id: ID de la session
        user_response: Objet UserResponse contenant les données à logger
    """
    ensure_csv_dir()
    filepath = get_session_csv_path(session_id)

    file_exists = os.path.exists(filepath)

    with open(filepath, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)

        if not file_exists:
            writer.writeheader()

        # Base data common to all evaluations
        base_row = {
            "timestamp": user_response.date_sent.isoformat(),
            "session_id": session_id,
            "question_id": user_response.question_id,
            "question_text": user_response.question_text,
            "user_answer": user_response.user_answer,
            "message_type": user_response.message_type or "",
        }

        # Write a row for each individual evaluation
        if user_response.individual_evaluations:
            for eval in user_response.individual_evaluations:
                row = {**base_row,
                       "score": eval.score,
                       "feedback": eval.feedback,
                       "model": eval.model,
                       "evaluation_type": "individual"
                      }
                writer.writerow(row)

        # Write a row for the final evaluation
        if user_response.evaluation:
            row = {**base_row,
                   "score": user_response.evaluation.score,
                   "feedback": user_response.evaluation.feedback,
                   "model": user_response.evaluation.model,
                   "evaluation_type": "final"
                  }
            writer.writerow(row)
