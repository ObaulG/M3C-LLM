#!/usr/bin/env python3
"""
Script de peuplement de la table text_answer_facts.

Pour k documents, pioche aléatoirement n questions/réponses existantes par document,
génère la liste des affirmations (faits) constituant chaque réponse de référence
via l'agent fact_extractor, les insère dans text_answer_facts,
et exporte un CSV (question_id, answer_id, réponse) des réponses couvertes.

Utilisation:
    python -m scripts.populate_answer_facts -n 3 -k 2
    python -m scripts.populate_answer_facts -n 5 --document-id dbd5f14a...

Le script suppose que la table text_answer_facts existe
(cf. database/sql_tables_scripts/create_answer_facts_table.sql).
"""

import argparse
import asyncio
import csv
import random
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.database import (
    get_db_connection,
    get_questions_by_document_id,
    insert_answer_facts,
    get_answer_ids_with_facts,
)
from agents.fact_extractor import get_fact_analyser_agent, FactExtractionInput


async def pick_questions_for_document(conn, document_id: str, n: int) -> List[Dict]:
    """Pioche n questions au hasard parmi celles du document (avec leurs réponses)."""
    questions = await get_questions_by_document_id(document_id, conn, include_answers=True)
    questions = [q for q in questions if q.get("answers")]
    if len(questions) > n:
        questions = random.sample(questions, n)
    return questions


async def extract_and_insert_facts(questions: List[Dict], conn, model: str, extraction_model: str) -> List[Dict]:
    """Extrait les affirmations de chaque réponse et les insère en base.

    Returns:
        List[Dict]: Liste des réponses couvertes
        (question_id, answer_id, answer_content), pour l'export CSV.
    """
    agent = get_fact_analyser_agent(model=extraction_model)
    covered = []
    for question in questions:
        for answer in question["answers"]:
            try:
                input_data = FactExtractionInput(paragraph=answer["content"])
                output = agent.run(input_data)
                facts = output.facts
            except Exception as e:
                print(f"[ERREUR] Extraction impossible pour answer_id={answer['answer_id']}: {e}")
                continue
            if not facts:
                print(f"[ATTENTION] Aucune affirmation extraite pour answer_id={answer['answer_id']}")
                continue
            await insert_answer_facts(answer["answer_id"], list(facts), conn, model=extraction_model)
            covered.append({
                "question_id": question["question_id"],
                "answer_id": answer["answer_id"],
                "reponse": answer["content"],
            })
            print(f"[OK] question {question['question_id']} / réponse {answer['answer_id']} : {len(facts)} affirmations insérées")
    return covered


def export_csv(covered: List[Dict], out_path: Path) -> None:
    """Écrit le CSV question_id, answer_id, réponse."""
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["question_id", "answer_id", "reponse"])
        writer.writeheader()
        writer.writerows(covered)


async def main():
    parser = argparse.ArgumentParser(description="Peuple text_answer_facts à partir de questions/réponses existantes.")
    parser.add_argument("-n", type=int, default=3, help="Nombre de questions par document (défaut: 3)")
    parser.add_argument("-k", type=int, default=1, help="Nombre de documents (défaut: 1)")
    parser.add_argument("--document-id", type=str, default=None,
                        help="Force un document précis (prioritaire sur -k)")
    parser.add_argument("--extraction-model", type=str, default="mistral-medium",
                        help="Modèle pour l'extraction des affirmations (défaut: mistral-medium)")
    parser.add_argument("--output", type=str, default=None, help="Chemin du CSV de sortie")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Ne pas ré-extraire les réponses ayant déjà des faits")
    parser.add_argument("--seed", type=int, default=None, help="Graine aléatoire pour la reproductibilité")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    # 1. Récupérer les documents candidats
    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT DISTINCT document_id FROM text_chunks")
            rows = await cur.fetchall()
        document_ids = [row[0] for row in rows]
    finally:
        conn.close()

    if not document_ids:
        print("Aucun document trouvé dans text_chunks.")
        return

    if args.document_id:
        selected_documents = [args.document_id]
    else:
        if len(document_ids) > args.k:
            selected_documents = random.sample(document_ids, args.k)
        else:
            selected_documents = document_ids[:args.k]
    print(f"Documents sélectionnés : {selected_documents}")

    # 2. Piocher les questions/réponses pour chaque document
    conn = await get_db_connection()
    all_questions: List[Dict] = []
    try:
        existing_answer_ids = await get_answer_ids_with_facts(conn) if args.skip_existing else set()
        for doc_id in selected_documents:
            questions = await pick_questions_for_document(conn, doc_id, args.n)
            if args.skip_existing:
                questions = [q for q in questions
                             if any(a["answer_id"] not in existing_answer_ids for a in q["answers"])]
            if not questions:
                print(f"[ATTENTION] Aucune question avec réponse pour le document {doc_id}")
                continue
            print(f"Document {doc_id} : {len(questions)} question(s) sélectionnée(s)")
            all_questions.extend(questions)
    finally:
        conn.close()

    if not all_questions:
        print("Aucune question/réponse à traiter.")
        return

    # 3. Extraire les affirmations et les insérer
    conn = await get_db_connection()
    try:
        covered = await extract_and_insert_facts(all_questions, conn, args.extraction_model, args.extraction_model)
    finally:
        conn.close()

    # 4. Export CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = Path(args.output) if args.output else results_dir / f"answer_facts_input_{timestamp}.csv"
    export_csv(covered, out_path)
    print(f"CSV écrit : {out_path} ({len(covered)} réponses)")


if __name__ == "__main__":
    asyncio.run(main())
