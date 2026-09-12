"""
Module pour le logging CSV des évaluations du message_evaluator_agent.

Ce module permet d'enregistrer les résultats des évaluations faites par l'agent
message_evaluator_agent, ainsi que les évaluations manuelles correspondantes,
dans un fichier CSV pour analyse ultérieure.

Un fichier CSV est créé dans le dossier question_answer/ avec le nom
message_evaluator_results.csv.
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# Dossier pour les logs CSV
CSV_DIR = "app/question_answer"
CSV_FILENAME = "message_evaluator_results.csv"

# Headers du CSV
CSV_HEADERS = [
    "timestamp",
    "document_id",
    "question_id",
    "question_text",
    "reference_answer",
    "user_answer",
    "agent_message_type",
    "agent_confidence",
    "agent_explanation",
    "manual_evaluation",
]


def ensure_csv_dir():
    """Crée le dossier de logging s'il n'existe pas."""
    Path(CSV_DIR).mkdir(parents=True, exist_ok=True)



def get_csv_path() -> str:
    """Retourne le chemin du CSV pour les évaluations."""
    return os.path.join(CSV_DIR, CSV_FILENAME)



def log_message_evaluator_result(
    document_id: str,
    question_id: int,
    question_text: str,
    reference_answer: str,
    user_answer: str,
    agent_message_type: str,
    agent_confidence: float,
    agent_explanation: str,
    manual_evaluation: Optional[bool] = None,
) -> str:
    """
    Ajoute une ligne au CSV des évaluations du message_evaluator_agent.
    Crée le fichier avec les headers si c'est le premier appel.

    Args:
        document_id: ID du document
        question_id: ID de la question
        question_text: Texte de la question
        reference_answer: Réponse de référence attendue
        user_answer: Réponse de l'utilisateur
        agent_message_type: Type de message selon l'agent
        agent_confidence: Niveau de confiance de l'agent
        agent_explanation: Explication de l'agent
        manual_evaluation: Évaluation manuelle (True=dans le contexte, False=hors sujet)

    Returns:
        str: Le chemin du fichier CSV
    """
    ensure_csv_dir()
    filepath = get_csv_path()

    file_exists = os.path.exists(filepath)

    # Formater l'évaluation manuelle pour le CSV
    manual_eval_str = ""
    if manual_evaluation is True:
        manual_eval_str = "dans_contexte"
    elif manual_evaluation is False:
        manual_eval_str = "hors_sujet"

    with open(filepath, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)

        if not file_exists:
            writer.writeheader()

        row = {
            "timestamp": datetime.now().isoformat(),
            "document_id": document_id,
            "question_id": question_id,
            "question_text": question_text,
            "reference_answer": reference_answer,
            "user_answer": user_answer,
            "agent_message_type": agent_message_type,
            "agent_confidence": agent_confidence,
            "agent_explanation": agent_explanation,
            "manual_evaluation": manual_eval_str,
        }
        writer.writerow(row)

    return filepath


def get_csv_file_path() -> str:
    """Retourne le chemin complet du fichier CSV."""
    return get_csv_path()
