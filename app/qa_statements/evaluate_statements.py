#!/usr/bin/env python3
"""Évaluation par vérification d'affirmations catégorisées.

Barème à trois catégories pour chaque réponse de référence :
- necessary : affirmations dont l'expression satisfait la demande ; seules
  elles comptent dans le score de complétude. Les reformulations et les
  informations déjà fournies par l'énoncé de la question sont acceptées.
- optional : compléments facultatifs ; signalés s'ils sont présents, mais leur
  absence ne réduit pas le score.
- errors : erreurs ou contradictions pertinentes ; leur présence dans la
  réponse du visiteur remet en cause sa validité.

Pour chaque ligne du CSV (question_id, visitor_answer) :
1. vérification de chaque affirmation nécessaire (présente ? + justification),
2. signalement des compléments facultatifs retrouvés,
3. détection des erreurs/contradictions dans la réponse du visiteur,
4. score de complétude = proportion d'affirmations nécessaires retrouvées,
   validité mise en cause si une erreur pertinente est détectée,
5. feedback rédigé séparément, sur le ton et l'exigence uniquement (ne doit
   pas exiger de détails facultatifs, ne pas répéter le contexte de la
   question, rester constructif).

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


class FeedbackOutput(BaseModel):
    """Feedback rédigé, indépendant du score de complétude."""
    feedback: str
    tone_appropriate: bool
    tone_comment: str


def reference_statements_by_question(data: Dict) -> Dict[int, Dict]:
    """Indexe le JSON : question_id -> {question_text, necessary, optional, errors}.

    Les affirmations sont regroupées par catégorie sur l'ensemble des réponses
    de référence correctes de la question. Les anciens JSON avec une simple
    liste « statements » sont rattachés à la catégorie necessary.
    """
    index = {}
    for question in all_questions_flat(data):
        necessary = []
        optional = []
        errors = []
        for answer in question.get("answers", []):
            if not answer.get("is_correct", True):
                continue
            statements = answer.get("statements", {})
            if isinstance(statements, dict):
                necessary.extend(statements.get("necessary", []))
                optional.extend(statements.get("optional", []))
                errors.extend(statements.get("errors", []))
            else:
                necessary.extend(statements)
        index[question["question_id"]] = {
            "question_text": question["question_text"],
            "necessary": necessary,
            "optional": optional,
            "errors": errors,
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
                    "L'affirmation est-elle présente dans la réponse du "
                    "visiteur ? Accepte toute reformulation fidèle et les "
                    "informations déjà fournies par l'énoncé de la question "
                    "(leur répétition n'est pas exigée). Réponds par un "
                    "booléen et une justification courte en français."
                ),
            }
        ],
    )


async def generate_feedback(
    client,
    model: str,
    question_text: str,
    visitor_answer: str,
    missing_necessary: List[str],
    present_optional: List[str],
) -> FeedbackOutput:
    """Rédige un feedback séparé du score : complétude et ton.

    Le feedback ne doit pas exiger les détails facultatifs, ne pas répéter le
    contexte de la question et rester constructif ; le LLM auto-évalue aussi
    son ton pour distinguer complétude et dureté du commentaire.
    """
    return client.chat.completions.create(
        model=model,
        response_model=FeedbackOutput,
        messages=[
            {
                "role": "user",
                "content": (
                    "Question posée au visiteur :\n"
                    f"{question_text}\n\n"
                    "Réponse du visiteur :\n"
                    f"{visitor_answer}\n\n"
                    "Affirmations nécessaires manquantes :\n"
                    + ("\n".join(f"- {s}" for s in missing_necessary) or "- aucune")
                    + "\n\nCompléments facultatifs présents :\n"
                    + ("\n".join(f"- {s}" for s in present_optional) or "- aucun")
                    + "\n\nRédige un feedback court en français à destination "
                    "du visiteur. Règles strictes : ne mentionne que les "
                    "affirmations nécessaires manquantes ; n'exige aucun "
                    "complément facultatif ; ne demande pas de répéter des "
                    "informations déjà données par la question ; reste "
                    "constructif, sans dureté ni exigence inutile. Évalue "
                    "ensuite honnêtement si ton propre feedback respecte ce "
                    "ton (tone_appropriate) et justifie (tone_comment)."
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
    """Évalue les réponses du CSV en vérifiant chaque affirmation catégorisée.

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
        necessary = question["necessary"]
        optional = question["optional"]
        errors = question["errors"]
        if not necessary:
            logger.warning(
                f"Question {question_id} : aucune affirmation nécessaire de référence"
            )

        necessary_checks = []
        for statement in necessary:
            check = await check_statement(
                client, model_name, statement, question["question_text"], visitor_answer
            )
            necessary_checks.append(check.model_dump())
            logger.info(
                f"Question {question_id} - nécessaire '{statement[:50]}...' : "
                f"{'présente' if check.present else 'absente'}"
            )

        optional_checks = []
        for statement in optional:
            check = await check_statement(
                client, model_name, statement, question["question_text"], visitor_answer
            )
            optional_checks.append(check.model_dump())
        present_optional = [c["statement"] for c in optional_checks if c["present"]]

        error_checks = []
        for statement in errors:
            check = await check_statement(
                client, model_name, statement, question["question_text"], visitor_answer
            )
            error_checks.append(check.model_dump())
        found_errors = [c["statement"] for c in error_checks if c["present"]]

        present_count = sum(1 for c in necessary_checks if c["present"])
        completeness_score = (
            round(present_count / len(necessary_checks), 3) if necessary_checks else None
        )
        valid = not found_errors

        missing_necessary = [c["statement"] for c in necessary_checks if not c["present"]]
        feedback = await generate_feedback(
            client, model_name, question["question_text"], visitor_answer,
            missing_necessary, present_optional,
        )

        results.append({
            "question_id": question_id,
            "question_text": question["question_text"],
            "visitor_answer": visitor_answer,
            "model": model_name,
            "necessary_checks": necessary_checks,
            "optional_checks": optional_checks,
            "error_checks": error_checks,
            "present_necessary_count": present_count,
            "total_necessary": len(necessary_checks),
            "present_optional": present_optional,
            "found_errors": found_errors,
            "completeness_score": completeness_score,
            "valid": valid,
            "feedback": feedback.feedback,
            "tone_appropriate": feedback.tone_appropriate,
            "tone_comment": feedback.tone_comment,
        })
        logger.info(
            f"Question {question_id} : complétude {completeness_score}, "
            f"validité {valid}, ton {'OK' if feedback.tone_appropriate else 'à revoir'}"
        )

    evaluated_scores = [
        r["completeness_score"] for r in results if r["completeness_score"] is not None
    ]
    report = {
        "input_csv": str(input_csv),
        "model": model_name,
        "results": results,
        "summary": {
            "nb_answers": len(results),
            "average_completeness_score": round(
                sum(evaluated_scores) / len(evaluated_scores), 3
            ) if evaluated_scores else None,
            "nb_valid": sum(1 for r in results if r["valid"]),
            "nb_tone_appropriate": sum(1 for r in results if r["tone_appropriate"]),
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
                "category",
                "present",
                "justification",
                "completeness_score",
            ],
        )
        writer.writeheader()
        for result in report["results"]:
            for category, checks in [
                ("necessary", result["necessary_checks"]),
                ("optional", result["optional_checks"]),
                ("error", result["error_checks"]),
            ]:
                for check in checks:
                    writer.writerow({
                        "question_id": result["question_id"],
                        "statement": check["statement"],
                        "category": category,
                        "present": check["present"],
                        "justification": check["justification"],
                        "completeness_score": result["completeness_score"],
                    })

    with open(md_out, "w", encoding="utf-8") as f:
        f.write("# Évaluation par vérification d'affirmations catégorisées\n\n")
        f.write(f"- Modèle : {report['model']}\n")
        f.write(f"- CSV d'entrée : {report['input_csv']}\n")
        summary = report["summary"]
        f.write(f"- Réponses évaluées : {summary['nb_answers']}\n")
        f.write(f"- Complétude moyenne : {summary['average_completeness_score']}\n")
        f.write(f"- Réponses valides (sans erreur pertinente) : {summary['nb_valid']}\n")
        f.write(f"- Feedbacks au ton approprié : {summary['nb_tone_appropriate']}\n\n")
        for result in report["results"]:
            f.write(f"## Question {result['question_id']}\n\n")
            f.write(f"> {result['question_text']}\n\n")
            f.write(f"**Réponse du visiteur** : {result['visitor_answer']}\n\n")
            f.write(
                f"**Complétude** : {result['completeness_score']} "
                f"({result['present_necessary_count']}/{result['total_necessary']} "
                f"affirmations nécessaires)\n\n"
            )
            f.write(f"**Validité** : {'oui' if result['valid'] else 'non'}\n\n")
            f.write("### Affirmations nécessaires\n\n")
            for check in result["necessary_checks"]:
                marker = "x" if check["present"] else " "
                f.write(f"- [{marker}] {check['statement']}\n")
                f.write(f"      - {check['justification']}\n")
            if result["optional_checks"]:
                f.write("\n### Compléments facultatifs (hors score)\n\n")
                for check in result["optional_checks"]:
                    marker = "x" if check["present"] else " "
                    f.write(f"- [{marker}] {check['statement']}\n")
            if result["found_errors"]:
                f.write("\n### Erreurs ou contradictions détectées\n\n")
                for statement in result["found_errors"]:
                    f.write(f"- {statement}\n")
            f.write(f"\n### Feedback\n\n{result['feedback']}\n\n")
            f.write(
                f"**Ton du feedback** : "
                f"{'approprié' if result['tone_appropriate'] else 'à revoir'} — "
                f"{result['tone_comment']}\n\n"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Évalue les réponses du visiteur en vérifiant les affirmations "
        "nécessaires, facultatives et les erreurs de la réponse de référence."
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
