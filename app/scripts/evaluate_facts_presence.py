#!/usr/bin/env python3
"""
Évaluation d'une réponse utilisateur par vérification d'affirmations.

Lit un CSV au format: question_id,reponse (la réponse du visiteur uniquement),
récupère les affirmations (faits) stockées dans text_answer_facts pour la
réponse de référence de chaque question, puis demande à un LLM, en UN SEUL
appel par question, de juger pour chaque affirmation si elle est présente,
partiellement présente ou absente de la réponse du visiteur.

Écrit un CSV de résultats: question_id, reponse, nb_faits, nb_present,
nb_partial, nb_absent, score, details (verdict par affirmation).

Utilisation:
    python -m scripts.evaluate_facts_presence --input answer_facts_input_<ts>.csv
"""

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.database import (
    get_db_connection,
    get_facts_by_question_ids,
)
from agents.fact_extractor import get_fact_presence_agent, FactPresenceInput, FactPresenceOutput

VERDICT_WEIGHTS = {
    "present": 1.0,
    "partial": 0.5,
    "absent": 0.0,
}

IMPORTANCE_WEIGHTS = {
    "essential": 3.0,
    "optional": 1.0,
}


def score_from_judgements(facts: List[Dict], judgements) -> float:
    """Score agrégé sur 10 : moyenne pondérée par verdict ET par importance.

    Un fait essentiel pèse 3 fois plus qu'un fait facultatif : son absence
    pénalise fortement le score, tandis que les faits facultatifs présents
    le consolident sans être requis.
    """
    if not judgements:
        return 0.0
    by_index = {j.fact_index: j for j in judgements}
    total = 0.0
    weight_sum = 0.0
    for i, fact in enumerate(facts):
        j = by_index.get(i)
        verdict = j.verdict if j else "absent"
        weight = IMPORTANCE_WEIGHTS.get(fact.get("importance", "essential"), IMPORTANCE_WEIGHTS["essential"])
        total += VERDICT_WEIGHTS.get(verdict, 0.0) * weight
        weight_sum += weight
    if weight_sum == 0:
        return 0.0
    return round(10.0 * total / weight_sum, 2)


def score_essential_coverage(facts: List[Dict], judgements) -> float:
    """Taux de couverture des faits essentiels uniquement (0-100%)."""
    by_index = {j.fact_index: j for j in judgements}
    essentials = [(i, f) for i, f in enumerate(facts) if f.get("importance", "essential") == "essential"]
    if not essentials:
        return ""
    total = sum(VERDICT_WEIGHTS.get(by_index[i].verdict if i in by_index else "absent", 0.0)
                for i, _ in essentials)
    return round(100.0 * total / len(essentials), 1)


async def evaluate_answer(agent, facts: List[Dict], user_answer: str) -> FactPresenceOutput:
    """Un seul appel LLM pour juger toutes les affirmations."""
    fact_contents = [f["content"] for f in facts]
    input_data = FactPresenceInput(user_answer=user_answer, facts=fact_contents)
    output = agent.run(input_data)
    return output


async def main():
    parser = argparse.ArgumentParser(description="Évalue une réponse utilisateur par vérification des affirmations stockées.")
    parser.add_argument("--input", type=str, required=True,
                        help="CSV des réponses visiteurs (colonnes: question_id, reponse)")
    parser.add_argument("--output", type=str, default=None, help="Chemin du CSV de résultats")
    parser.add_argument("--model", type=str, default="mistral-medium",
                        help="Modèle pour le jugement de présence (défaut: mistral-medium)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Fichier introuvable : {input_path}")
        return

    # 1. Charger les réponses visiteurs
    rows: List[Dict] = []
    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            question_id = int(row["question_id"])
            rows.append({"question_id": question_id, "reponse": row["reponse"]})

    if not rows:
        print("Aucune ligne dans le CSV d'entrée.")
        return

    # 2. Récupérer les affirmations des réponses de référence
    question_ids = list({r["question_id"] for r in rows})
    conn = await get_db_connection()
    try:
        facts_by_question = await get_facts_by_question_ids(question_ids, conn)
    finally:
        conn.close()

    agent = get_fact_presence_agent(model=args.model)

    # 3. Évaluer chaque réponse : un seul appel LLM par question
    results: List[Dict] = []
    for row in rows:
        question_id = row["question_id"]
        facts = facts_by_question.get(question_id, [])
        if not facts:
            print(f"[ATTENTION] Aucune affirmation stockée pour question_id={question_id}, ignorée.")
            results.append({
                "question_id": question_id,
                "reponse": row["reponse"],
                "nb_faits": 0,
                "nb_essentiels": 0,
                "nb_present": 0,
                "nb_partial": 0,
                "nb_absent": 0,
                "score": "",
                "couverture_essentiels": "",
                "details": "aucun fait stocké",
            })
            continue

        try:
            output = await evaluate_answer(agent, facts, row["reponse"])
            judgements = output.judgements
        except Exception as e:
            print(f"[ERREUR] Jugement impossible pour question_id={question_id}: {e}")
            continue

        # Aligner les verdicts sur les faits (par fact_index)
        by_index = {j.fact_index: j for j in judgements}
        details = []
        nb = {"present": 0, "partial": 0, "absent": 0}
        for i, fact in enumerate(facts):
            j = by_index.get(i)
            verdict = j.verdict if j else "absent"
            if verdict not in nb:
                verdict = "absent"
            nb[verdict] += 1
            details.append({"fact_id": fact["fact_id"], "fact": fact["content"],
                            "importance": fact.get("importance", "essential"),
                            "verdict": verdict,
                            "justification": j.justification if j else ""})

        score = score_from_judgements(facts, judgements)
        essential_coverage = score_essential_coverage(facts, judgements)
        nb_essential = sum(1 for f in facts if f.get("importance", "essential") == "essential")
        results.append({
            "question_id": question_id,
            "reponse": row["reponse"],
            "nb_faits": len(facts),
            "nb_essentiels": nb_essential,
            "nb_present": nb["present"],
            "nb_partial": nb["partial"],
            "nb_absent": nb["absent"],
            "score": score,
            "couverture_essentiels": essential_coverage,
            "details": json.dumps(details, ensure_ascii=False),
        })
        print(f"[OK] question {question_id} : {nb['present']} present / {nb['partial']} partial / "
              f"{nb['absent']} absent -> score {score}/10 "
              f"(couverture essentiels: {essential_coverage}%)")

    # 4. Export des résultats
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = Path(args.output) if args.output else results_dir / f"facts_presence_results_{timestamp}.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "question_id", "reponse", "nb_faits", "nb_essentiels", "nb_present", "nb_partial", "nb_absent",
            "score", "couverture_essentiels", "details",
        ])
        writer.writeheader()
        writer.writerows(results)
    print(f"Résultats écrits : {out_path} ({len(results)} évaluations)")


if __name__ == "__main__":
    asyncio.run(main())
