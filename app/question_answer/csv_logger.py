import csv
import os
from datetime import datetime
from pathlib import Path

CSV_NAME = "question_answer_evals.csv"

CSV_HEADERS = [
    "timestamp",
    "question_id",
    "question_text",
    "user_answer",
    "score",
    "feedback",
    "model",
    "time",
    "input_tokens",
    "output_tokens"

]

def log_response_to_csv(evaluation_input,
                        evalution_result,
                        question_id: int,
                        elapsed_time: float) -> None:
    """
    Ajoute une ou plusieurs lignes au CSV de la session (une par évaluation).
    Crée le fichier avec les headers si c'est le premier appel pour cette session.

    Args:
        session_id: ID de la session
        user_response: Objet UserEvaluationResponse contenant les données à logger
    """


    with open(CSV_NAME, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)

        file_exists = os.path.exists(CSV_NAME)
        if not file_exists:
            writer.writeheader()

        # Base data common to all evaluations
        base_row = {
            "timestamp": datetime.now(),
            "question_id": question_id,
            "question_text": evaluation_input.question,
            "user_answer": evaluation_input.user_answer,
            "score": evalution_result.score,
            "feedback": evalution_result.feedback,
            "model": evalution_result.model,
            "time": elapsed_time,
            "input_tokens": evalution_result.input_tokens,
            "output_tokens": evalution_result.output_tokens
        }

        writer.writerow(base_row)
        print("réponse ajoutée dans", CSV_NAME)

