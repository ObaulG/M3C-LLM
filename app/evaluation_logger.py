# evaluation_logger.py
"""
Module pour le logging des évaluations de réponses dans le fichier question-answer-reference-eval.

Ce module permet d'enregistrer les évaluations (automatiques et manuelles) des réponses
aux questions de référence, pour permettre une analyse et un suivi des performances.
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Chemin vers le fichier d'évaluation
EVALUATION_CSV_PATH = "question-answer-reference-eval.csv"

# En-têtes du CSV
CSV_HEADERS = [
    "question_id",
    "answer_id", 
    "evaluated_answer",
    "score",
    "feedback",
    "evaluation_type",  # 'auto' ou 'manual'
    "evaluation_source",  # 'llm' ou 'user' - source de la réponse évaluée
    "evaluation_date",
    "model_used",  # Modèle utilisé pour l'évaluation automatique
    "question_content",
    "reference_answer"
]


def ensure_evaluation_csv():
    """Crée le fichier CSV avec les headers s'il n'existe pas, ou met à jour les headers si nécessaire."""
    file_path = Path(EVALUATION_CSV_PATH)
    if not file_path.exists():
        with open(file_path, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
            writer.writeheader()
    else:
        # Vérifier si les headers sont à jour
        with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            existing_headers = reader.fieldnames or []
        
        # Si des headers manquents, les ajouter
        missing_headers = [h for h in CSV_HEADERS if h not in existing_headers]
        if missing_headers:
            # Lire toutes les lignes existantes
            with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
                rows = list(csv.DictReader(csvfile))
            
            # Réécrire avec les nouveaux headers
            with open(file_path, mode='w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)


def log_evaluation_to_csv(evaluation_data: Dict[str, Any]) -> str:
    """
    Ajoute une évaluation au fichier CSV.
    
    Args:
        evaluation_data: Dictionnaire contenant les données d'évaluation avec les clés:
            - question_id: ID de la question
            - answer_id: ID de la réponse de référence
            - evaluated_answer: Réponse qui a été évaluée
            - score: Note (1-10)
            - feedback: Commentaire sur l'évaluation
            - evaluation_type: 'auto' ou 'manual'
            - model_used: Modèle utilisé (pour l'auto-évaluation)
            - question_content: Contenu de la question
            - reference_answer: Réponse de référence
    
    Returns:
        Chemin du fichier CSV
    """
    ensure_evaluation_csv()
    
    # S'assurer que toutes les clés sont présentes
    row_data = {header: evaluation_data.get(header, "") for header in CSV_HEADERS}
    row_data["evaluation_date"] = datetime.now().isoformat()
    
    with open(EVALUATION_CSV_PATH, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
        writer.writerow(row_data)
    
    return EVALUATION_CSV_PATH


def get_reference_answers() -> Dict[int, str]:
    """
    Charge le fichier question-answer-reference.csv et retourne un mapping
    question_id -> (answer_id, question_content, response_answer).
    
    Returns:
        Dictionnaire avec les questions et réponses de référence
    """
    reference_file = "../question-answer-reference.csv"
    reference_data = {}
    
    if not os.path.exists(reference_file):
        return reference_data
    
    try:
        with open(reference_file, mode='r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                question_id = int(row.get('question_id', 0))
                reference_data[question_id] = {
                    'answer_id': row.get('answer_id', ''),
                    'question_content': row.get('question_content', ''),
                    'response_answer': row.get('response_answer', '')
                }
    except Exception as e:
        print(f"Erreur lors du chargement du fichier de référence: {e}")
    
    return reference_data


def get_reference_answer(question_id: int) -> Dict[str, str]:
    """
    Récupère la réponse de référence pour une question donnée.
    
    Args:
        question_id: ID de la question
    
    Returns:
        Dictionnaire avec answer_id, question_content, response_answer ou None
    """
    reference_answers = get_reference_answers()
    return reference_answers.get(question_id)
