#!/usr/bin/env python3
"""Évaluation par vérification d'affirmations.

Pour chaque ligne du CSV de réponses (question_id, visitor_answer), regroupe les
affirmations des réponses de référence correctes de la question, puis demande au
LLM, pour chaque affirmation, si elle est présente dans la réponse du visiteur
(booléen + justification). Le score d'une réponse est la proportion
d'affirmations retrouvées.

Usage (depuis la racine du dépôt) :
    python -m app.qa_statements.evaluate_statements --input answers_input_template.csv
"""

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.qa_statements.utils import (
    RESULTS_DIR,
    all_questions_flat,
    get_llm_client,
    load_json,
    timestamped_filename,
)

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

FALLBACK_MODEL = "mistral-medium"


class StatementCheck(BaseModel):
    """Résultat de la vérification d'une affirmation dans la réponse du visiteur."""
    statement: str
    present: bool
    justification: str


def reference_statements_by_question(data: Dict) -> Dict[int, Dict]:
    """Indexe le JSON : question_id -> {question_text, statements (réponses correctes)}."""
    index = {}
    for question in all_questions_flat(data):
        statements = [
            statement
            for answer in question.get("answers", [])
            if answer.get("is_correct", True)
            for statement in answer.get("statements", [])
        ]
        index[question["question_id"]] = {
            "question_text": question["question_text"],
            "statements": statements,
        }
    return index


async def check_statement(
    client,
    model: str,
    statement: str,
    question_text: str,
    visitor_answer: str,
) -> StatementCheck:
    """Demande au LLM si l'affirmation est présente dans la réponse du visiteur."""
    return client.chat.completions.create(
        model=model,
        response_model=StatementCheck,
        messages=[
            {
                "role": "user",
                "content": (
                    "Question posée au visiteur :\n"
                    f"{question_text}\n\n"
                    "Réponse rédigée par le visiteur :\n"
                    f"{visitor_answer}\n\n"
                    "Affirmation à vérifier :\n"
                    f"{statement}\n\n"
                    "L'affirmation est-elle présente dans la réponse du visiteur, "
                    "même reformulée ou implicite ? Réponds par un booléen et une "
                    "justification courte en français."
                ),
            }
        ],
    )


async def evaluate_statements(
    input_csv: Path,
    provider: str = "mistral",
    model: Optional[str] = None,
    json_path: Optional[Path] = None,
    results_dir: Path = RESULTS_DIR,
) -> Dict:
    """Évalue les réponses du CSV en vérifiant chaque affirmation.

    Args:
        input_csv: CSV avec les colonnes question_id,visitor_answer.
        provider: fournisseur LLM ("mistral" ou "ollama").
        model: nom du modèle LLM (défaut : mistral-medium).
        json_path: chemin du JSON de données (défaut : qa_statements.json).
        results_dir: dossier de sortie des résultats.

    Returns:
        Le rapport complet d'évaluation (dict).
    """
    data = load_json(json_path) if json_path else load_json()
    index = reference_statements_by_question(data)
    client = get_llm_client(provider, model)
    model_name = model or FALLBACK_MODEL

    with open(input_csv, "r", encoding="utf-8") as f:
        rows = [row for row in csv.DictReader(f) if (row.get("visitor_answer") or "").strip()]

    if not rows:
        raise SystemExit(f"Aucune réponse visiteur remplie dans {input_csv}")

    results = []
    for row in rows:
        question_id = int(row["question_id"])
        visitor_answer = row["visitor_answer"].strip()
        if question_id not in index:
            logger.warning(f"Question {question_id} absente du JSON, ignorée")
            continue

        question = index[question_id]
        statements = question["statements"]
        if not statements:
            logger.warning(f"Question {question_id} : aucune affirmation de référence")

        checks = []
        for statement in statements:
            check = await check_statement(
                client, model_name, statement, question["question_text"], visitor_answer
            )
            checks.append(check.model_dump())
            logger.info(
                f"Question {question_id} - affirmation '{statement[:50]}...' : "
                f"{'présente' if check.present else 'absente'}"
            )

        present_count = sum(1 for c in checks if c["present"])
        score = round(present_count / len(checks), 3) if checks else None
        results.append({
            "question_id": question_id,
            "question_text": question["question_text"],
            "visitor_answer": visitor_answer,
            "model": model_name,
            "statements_checks": checks,
            "present_count": present_count,
            "total_statements": len(checks),
            "score": score,
        })

    evaluated_scores = [r["score"] for r in results if r["score"] is not None]
    report = {
        "input_csv": str(input_csv),
        "model": model_name,
        "results": results,
        "summary": {
            "nb_answers": len(results),
            "average_score": round(sum(evaluated_scores) / len(evaluated_scores), 3)
            if evaluated_scores
            else None,
        },
    }

    results_dir.mkdir(parents=True, exist_ok=True)
    json_out = results_dir / timestamped_filename("statements_evaluation", "json")
    csv_out = results_dir / timestamped_filename("statements_evaluation", "csv")
    md_out = results_dir / timestamped_filename("statements_evaluation_report", "md")
    write_outputs(report, json_out, csv_out, md_out)

    logger.info(f"Résultats : {json_out}")
    return report


def write_outputs(report: Dict, json_out: Path, csv_out: Path, md_out: Path) -> None:
    """Écrit les résultats en JSON, CSV et rapport Markdown."""
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with open(csv_out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "question_id",
                "statement",
                "present",
                "justification",
                "score",
            ],
        )
        writer.writeheader()
        for result in report["results"]:
            for check in result["statements_checks"]:
                writer.writerow({
                    "question_id": result["question_id"],
                    "statement": check["statement"],
                    "present": check["present"],
                    "justification": check["justification"],
                    "score": result["score"],
                })

    with open(md_out, "w", encoding="utf-8") as f:
        f.write("# Évaluation par vérification d'affirmations\n\n")
        f.write(f"- Modèle : {report['model']}\n")
        f.write(f"- CSV d'entrée : {report['input_csv']}\n")
        summary = report["summary"]
        f.write(f"- Réponses évaluées : {summary['nb_answers']}\n")
        f.write(f"- Score moyen : {summary['average_score']}\n\n")
        for result in report["results"]:
            f.write(f"## Question {result['question_id']}\n\n")
            f.write(f"> {result['question_text']}\n\n")
            f.write(f"**Réponse du visiteur** : {result['visitor_answer']}\n\n")
            f.write(
                f"**Score** : {result['score']} "
                f"({result['present_count']}/{result['total_statements']} affirmations)\n\n"
            )
            for check in result["statements_checks"]:
                marker = "x" if check["present"] else " "
                f.write(f"- [{marker}] {check['statement']}\n")
                f.write(f"      - {check['justification']}\n")
            f.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Évalue les réponses du visiteur en vérifiant chaque affirmation "
        "de la réponse de référence."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="CSV avec les colonnes question_id,visitor_answer",
    )
    parser.add_argument(
        "--provider",
        choices=["mistral", "ollama"],
        default="mistral",
        help="Fournisseur LLM (défaut : mistral)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Nom du modèle LLM (défaut : mistral-medium)",
    )
    args = parser.parse_args()

    asyncio.run(
        evaluate_statements(
            input_csv=args.input,
            provider=args.provider,
            model=args.model,
        )
    )


if __name__ == "__main__":
    main()
