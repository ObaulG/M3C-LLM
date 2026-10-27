#!/usr/bin/env python3
"""Export CSV des réponses de visiteur.

Écrit un CSV avec les colonnes question_id,visitor_answer : une ligne par
question du jeu de données qa_statements.json, la colonne visitor_answer étant
laissée vide pour être remplie avec la réponse rédigée du visiteur.

Usage (depuis la racine du dépôt) :
    python -m app.qa_statements.export_answers_csv --output answers_input_template.csv
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.qa_statements.utils import DIR_PATH, all_questions_flat, load_json

DEFAULT_OUTPUT = DIR_PATH / "answers_input_template.csv"
CSV_COLUMNS = ["question_id", "visitor_answer"]


def export_answers_csv(output: Path = DEFAULT_OUTPUT, json_path: Path = None) -> Path:
    """Génère le CSV des réponses visiteur à partir de qa_statements.json.

    Args:
        output: chemin du CSV de sortie.
        json_path: chemin du JSON de données (défaut : qa_statements.json).

    Returns:
        Le chemin du CSV écrit.
    """
    data = load_json(json_path) if json_path else load_json()
    questions = all_questions_flat(data)
    if not questions:
        raise SystemExit(
            "qa_statements.json ne contient aucune question ; lancez d'abord "
            "python -m app.qa_statements.build_dataset"
        )

    with open(output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for question in questions:
            writer.writerow({
                "question_id": question["question_id"],
                "visitor_answer": "",
            })
    return output


def main():
    parser = argparse.ArgumentParser(
        description="Écrit le CSV question_id,visitor_answer à remplir pour l'évaluation."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Chemin du CSV de sortie (défaut : {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    output = export_answers_csv(output=args.output)
    print(f"CSV écrit : {output}")


if __name__ == "__main__":
    main()
