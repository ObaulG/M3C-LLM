#!/usr/bin/env python3
"""
Script pour évaluer les réponses du CSV question-answer-reference-eval.csv
avec les modèles locaux Ollama définis dans instructor_factory.py.

Pour chaque ligne du CSV avec une evaluated_answer non vide, ce script :
1. Utilise chaque modèle Ollama pour évaluer la réponse
2. Ajoute les résultats dans un nouveau CSV

Usage:
    python evaluate_with_local_models.py [--limit N] [--output FILE]
    
Args:
    --limit N: Limiter à N lignes pour les tests (défaut: toutes)
    --output FILE: Nom du fichier de sortie (défaut: question-answer-reference-eval-with-local.csv)
"""

import argparse
import asyncio
import csv
import json
import re
from datetime import datetime
from pathlib import Path
import sys
import time

# Ajouter le dossier parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.instructor_factory import OLLAMA_MODELS
from agents.answer_evaluator_agent import get_evaluator_agent_local, EvaluateRequestInput, run_raw, \
    AgentEvaluationResult, get_evaluator_agent_local_bis
from agents.token_monitor import monitor_agent_call_async


def parse_json_response(response_text: str) -> dict:
    """
    Parse une réponse JSON qui peut être dans un bloc ```json ou JSON brut.
    
    Args:
        response_text: La réponse texte du modèle
        
    Returns:
        dict: Le dictionnaire JSON parsé
        
    Raises:
        ValueError: Si le JSON est invalide
    """
    # Chercher le bloc ```json
    match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # Essayer de trouver du JSON brut
        # Nettoyer les éventuels markers de markdown
        json_str = response_text.strip()
        if json_str.startswith('```') and json_str.endswith('```'):
            json_str = json_str[3:-3].strip()
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Réponse JSON invalide: {response_text}\nErreur: {e}")


async def evaluate_row_with_model(row: dict, model: str) -> dict:
    """
    Évalue une ligne du CSV avec un modèle Ollama spécifique.
    
    Args:
        row: Dictionnaire représentant une ligne du CSV
        model: Nom du modèle Ollama à utiliser
        
    Returns:
        dict: Une nouvelle ligne avec les résultats de l'évaluation
    """
    # Créer l'agent d'évaluation pour ce modèle
    try:
        evaluator = get_evaluator_agent_local_bis(model=model, provider="ollama", async_mode=True)
    except Exception as e:
        raise RuntimeError(f"Échec de la création de l'agent pour le modèle {model}: {e}")

    input_data = EvaluateRequestInput(
        question=row['question_content'],
        expected_answers=[row['reference_answer']],
        user_answer=row['evaluated_answer'],
        model=model
    )

    # Mesurer le temps d'exécution et capturer les tokens
    start_time = time.time()
    
    try:
        # Utiliser monitor_agent_call_async pour obtenir les informations de tokens
        result, input_token_result, output_tokens = await monitor_agent_call_async(
            evaluator,
            user_input=input_data,
            method="run_async"
        )
    except Exception as e:
        raise RuntimeError(f"Échec de l'évaluation avec {model} pour question_id {row.get('question_id', 'N/A')}: {e}")
    
    execution_time = time.time() - start_time
    
    # Créer une nouvelle ligne avec les résultats
    new_row = row.copy()
    new_row['score'] = result.score
    new_row['feedback'] = result.feedback
    new_row['model_used'] = model
    new_row['evaluation_date'] = datetime.now().isoformat()
    new_row['evaluation_source'] = 'auto'
    new_row['evaluation_type'] = 'local'
    
    # Ajouter les métriques de performance
    new_row['execution_time_seconds'] = f"{execution_time:.4f}"
    new_row['input_tokens'] = input_token_result
    new_row['output_tokens'] = output_tokens
    new_row['total_tokens'] = input_token_result + output_tokens
    
    return new_row


async def main(limit=None, output_file=None, models = OLLAMA_MODELS):
    """Fonction principale du script."""
    
    # Chemins des fichiers
    input_csv_path = Path(__file__).parent.parent.parent / "question-answer-reference-eval.csv"
    
    # Déterminer le nom du fichier de sortie
    if output_file:
        output_csv_path = Path(output_file)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_csv_path = Path(__file__).parent.parent.parent / f"question-answer-reference-eval-with-local_{timestamp}.csv"
    
    print(f"Lecture du CSV: {input_csv_path}")
    print(f"Modèles à utiliser: {OLLAMA_MODELS}")
    print(f"Écriture des résultats dans: {output_csv_path}")
    print()
    
    # Lire le CSV existant
    try:
        with open(input_csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            original_rows = list(reader)
    except FileNotFoundError:
        raise FileNotFoundError(f"Fichier CSV introuvable: {input_csv_path}")
    except Exception as e:
        raise RuntimeError(f"Erreur lors de la lecture du CSV: {e}")
    
    print(f"Nombre de lignes à évaluer: {len(original_rows)}")
    print()
    
    # Filtrer les lignes avec evaluated_answer non vide
    rows_to_evaluate = [row for row in original_rows if row.get('evaluated_answer', '').strip()]
    
    # Appliquer la limite si spécifiée
    if limit is not None and limit > 0:
        rows_to_evaluate = rows_to_evaluate[:limit]
        print(f"Limité à {limit} lignes pour le test")
    
    print(f"Lignes avec evaluated_answer non vide: {len(rows_to_evaluate)}")
    print()
    
    # Déterminer les colonnes (toutes les clés du premier dictionnaire)
    fieldnames = list(original_rows[0].keys()) if original_rows else []
    
    # Ajouter les nouveaux champs pour le tracking de performance
    additional_fields = ['execution_time_seconds', 'input_tokens', 'output_tokens', 'total_tokens']
    for field in additional_fields:
        if field not in fieldnames:
            fieldnames.append(field)
    
    # Écrire les lignes originales dans le CSV
    try:
        with open(output_csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(original_rows)
        total_written = len(original_rows)
    except Exception as e:
        raise RuntimeError(f"Erreur lors de l'écriture du CSV initial: {e}")
    
    # Préparer le compteur total de nouvelles lignes
    total_new_rows = 0
    
    # Pour chaque modèle
    for model in models:
        print(f"\n=== Évaluation avec le modèle: {model} ===")
        
        model_start_time = time.time()
        model_success_count = 0
        model_error_count = 0
        model_total_input_tokens = 0
        model_total_output_tokens = 0
        
        # Ouvrir le CSV en mode append pour ce modèle
        with open(output_csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            # Pour chaque ligne à évaluer
            for i, row in enumerate(rows_to_evaluate, 1):
                question_id = row.get('question_id', 'N/A')
                
                try:
                    # Évaluer avec ce modèle
                    new_row = await evaluate_row_with_model(row, model)
                    print(new_row)
                    
                    # Accumuler les stats de tokens pour ce modèle
                    model_total_input_tokens += new_row.get('input_tokens', 0)
                    model_total_output_tokens += new_row.get('output_tokens', 0)
                    
                    # Écrire la ligne dans le CSV immédiatement
                    writer.writerow(new_row)
                    
                    model_success_count += 1
                    total_new_rows += 1
                    
                    # Afficher la progression
                    if i % 5 == 0 or i == len(rows_to_evaluate):
                        print(f"  [{i}/{len(rows_to_evaluate)}] question_id={question_id} - score={new_row['score']}")
                    
                except Exception as e:
                    model_error_count += 1
                    print(f"  [ERREUR] question_id={question_id}: {e}")
                    # Ajouter une ligne avec erreur
                    error_row = row.copy()
                    error_row['score'] = ''
                    error_row['feedback'] = f"Erreur d'évaluation: {str(e)}"
                    error_row['model_used'] = model
                    error_row['evaluation_date'] = datetime.now().isoformat()
                    error_row['evaluation_source'] = 'auto'
                    error_row['evaluation_type'] = 'local'
                    # Ajouter les champs de tracking pour les erreurs
                    error_row['execution_time_seconds'] = ''
                    error_row['input_tokens'] = ''
                    error_row['output_tokens'] = ''
                    error_row['total_tokens'] = ''
                    
                    # Écrire la ligne d'erreur dans le CSV immédiatement
                    writer.writerow(error_row)
                    
                    total_new_rows += 1
        
        model_end_time = time.time()
        model_duration = model_end_time - model_start_time
        
        print(f"\nModèle {model} terminé:")
        print(f"  Succès: {model_success_count}")
        print(f"  Échecs: {model_error_count}")
        print(f"  Durée totale: {model_duration:.2f} secondes")
        print(f"  Durée moyenne par évaluation: {model_duration / len(rows_to_evaluate):.2f}s" if len(rows_to_evaluate) > 0 else "")
        print(f"  Tokens d'entrée totaux: {model_total_input_tokens}")
        print(f"  Tokens de sortie totaux: {model_total_output_tokens}")
        print(f"  Tokens totaux: {model_total_input_tokens + model_total_output_tokens}")
        if model_success_count > 0:
            print(f"  Tokens d'entrée moyens: {model_total_input_tokens / model_success_count:.1f}")
            print(f"  Tokens de sortie moyens: {model_total_output_tokens / model_success_count:.1f}")
        print()
    
    if total_new_rows == 0 and len(rows_to_evaluate) > 0:
        print("Aucune nouvelle ligne ajoutée!")
    else:
        print(f"\n✓ CSV généré avec succès: {output_csv_path}")
        print(f"  Nombre total de lignes: {total_written + total_new_rows}")
        print(f"  Lignes originales: {total_written}")
        print(f"  Nouvelles lignes ajoutées: {total_new_rows}")


if __name__ == "__main__":
    # Parser les arguments
    parser = argparse.ArgumentParser(
        description="Évaluer les réponses avec les modèles Ollama locaux"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limiter à N lignes pour les tests"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Nom du fichier de sortie CSV"
    )
    
    args = parser.parse_args()
    models = ["gemma4:e2b", "llama3.2:1b", "llama3.2:3b", "mistral:7b"]
    try:
        asyncio.run(main(limit=args.limit, output_file=args.output, models=models))
    except KeyboardInterrupt:
        print("\n\nScript interrompu par l'utilisateur.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nErreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
