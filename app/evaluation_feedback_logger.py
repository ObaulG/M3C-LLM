# evaluation_feedback_logger.py
"""
Module pour le logging des feedbacks humains sur les évaluations IA.

Ce module permet d'enregistrer les critiques humaines sur les évaluations
générées par l'IA (note + commentaire) pour permettre une analyse de qualité
et un amélioration continue du système.
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Chemin vers le fichier de feedback
FEEDBACK_CSV_PATH = "evaluation-feedback.csv"

# En-têtes du CSV pour les feedbacks sur les évaluations IA
FEEDBACK_CSV_HEADERS = [
    "question_id",
    "chunk_id",
    "question_content",
    "user_answer",
    "ai_score",
    "ai_feedback",
    "human_rating",
    "human_comment",
    "evaluation_date"
]


def ensure_feedback_csv():
    """Crée le fichier CSV avec les headers s'il n'existe pas, ou met à jour les headers si nécessaire."""
    file_path = Path(FEEDBACK_CSV_PATH)
    if not file_path.exists():
        with open(file_path, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=FEEDBACK_CSV_HEADERS)
            writer.writeheader()
    else:
        # Vérifier si les headers sont à jour
        try:
            with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                existing_headers = reader.fieldnames or []
            
            # Si des headers manquents, les ajouter
            missing_headers = [h for h in FEEDBACK_CSV_HEADERS if h not in existing_headers]
            if missing_headers:
                # Lire toutes les lignes existantes
                with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
                    rows = list(csv.DictReader(csvfile))
                
                # Réécrire avec les nouveaux headers
                with open(file_path, mode='w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=FEEDBACK_CSV_HEADERS)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow(row)
        except Exception as e:
            print(f"Erreur lors de la vérification du CSV de feedback: {e}")


def log_feedback_to_csv(feedback_data: Dict[str, Any]) -> str:
    """
    Ajoute un feedback humain sur une évaluation IA au fichier CSV.
    
    Args:
        feedback_data: Dictionnaire contenant les données de feedback avec les clés:
            - question_id: ID de la question
            - chunk_id: ID du chunk (optionnel)
            - question_content: Contenu de la question (optionnel)
            - user_answer: Réponse qui a été évaluée
            - ai_score: Note générée par l'IA
            - ai_feedback: Commentaire généré par l'IA
            - human_rating: Note humaine sur l'évaluation IA (1-10)
            - human_comment: Commentaire humain sur l'évaluation IA (optionnel)
    
    Returns:
        Chemin du fichier CSV
    """
    ensure_feedback_csv()
    
    # S'assurer que toutes les clés sont présentes
    row_data = {header: feedback_data.get(header, "") for header in FEEDBACK_CSV_HEADERS}
    row_data["evaluation_date"] = datetime.now().isoformat()
    
    with open(FEEDBACK_CSV_PATH, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FEEDBACK_CSV_HEADERS)
        writer.writerow(row_data)
    
    return FEEDBACK_CSV_PATH
