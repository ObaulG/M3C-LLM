#!/usr/bin/env python3
"""
Évaluation des réponses du dataset ROARs avec les agents du projet.

Pipeline:
1. Pour chaque question du dataset (ROARS_texts.csv), génère une réponse de
   référence à partir de la question et du passage correspondant (agent QA),
   puis la décompose en faits via l'agent answer_facts. Résultat stocké dans
   test-ROARs/roars_answer_facts.json (réutilisé s'il existe déjà).
2. Pour chaque ligne de ROARS_data.csv et chaque modèle (ministral-3b, -8b,
   -14b), appelle l'agent d'évaluateur deux fois:
   - avec la réponse de référence simple -> score_simple_<modèle>
   - avec la liste des faits de réponse   -> score_faits_<modèle>
   Chaque score est un entier entre 1 et 10; -1 en cas d'erreur LLM.
3. Écrit test-ROARs/ROARS_data_evaluated.csv: colonnes d'origine du dataset
   + les 6 colonnes de scores. Les scores déjà présents (et <> -1) ne sont
   pas recalculés; les lignes sans résultat (ou -1) sont retraitées.

Utilisation:
    python -m scripts.evaluate_roars
    python -m scripts.evaluate_roars --limit 5
    python -m scripts.evaluate_roars --facts-model ministral-8b-2512
"""

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.answer_evaluator_agent import (
    EvaluateRequestInput,
    get_evaluator_agent,
)
from agents.fact_extractor import (
    FactExtractionInput,
    get_answer_facts_agent,
)
from agents.qa_single_agent import get_qa_agent, QuestionRequestInput

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ROARS_DIR = Path(__file__).resolve().parent.parent.parent / "test-ROARs"
FACTS_FILE = ROARS_DIR / "roars_answer_facts.json"
DATA_FILE = ROARS_DIR / "ROARS_data.csv"
TEXTS_FILE = ROARS_DIR / "ROARS_texts.csv"
OUTPUT_FILE = ROARS_DIR / "ROARS_data_evaluated.csv"

# Nom court -> nom de modèle de l'API Mistral (cf. agents/instructor_factory.py)
EVALUATION_MODELS = {
    "ministral-3b": "ministral-3b-2512",
    "ministral-8b": "ministral-8b-2512",
    "ministral-14b": "ministral-14b-2512",
}
FACTS_MODEL_DEFAULT = "ministral-3b-2512"
MAX_RETRIES = 2


def load_texts():
    """Charge ROARS_texts.csv -> {text_id: text}, indexé par type."""
    texts = {}
    with open(TEXTS_FILE, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            texts[row["text_id"]] = row["text"].strip()
    return texts


def build_question_passage_map():
    """Texte du passage de chaque question.

    Utilise la colonne "relevant_passage" de ROARS_data.csv si elle est
    présente, sinon le passage identifié par passage_id dans ROARS_texts.csv.
    """
    texts = load_texts()
    mapping = {}
    with open(DATA_FILE, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            qid = row["question_id"]
            if qid in mapping:
                continue
            if row.get("relevant_passage", "").strip():
                mapping[qid] = row["relevant_passage"].strip()
            else:
                mapping[qid] = texts.get(row["passage_id"], "")
    return mapping


def build_reference_answers(facts_model: str) -> dict:
    """Génère (ou recharge) la réponse de référence + les faits de chaque question.

    Returns:
        dict: {question_id: {"answer": str, "facts": [{"content", "importance"}]}}
    """
    if FACTS_FILE.exists():
        with open(FACTS_FILE, encoding="utf-8") as f:
            existing = json.load(f)
        if existing.get("model") == facts_model and existing.get("questions"):
            logger.info("Faits de réponse déjà présents dans %s", FACTS_FILE)
            return existing["questions"]
        logger.info("Modèle de génération différent, régénération des faits.")

    texts = load_texts()
    passage_map = build_question_passage_map()
    question_ids = sorted(passage_map)
    qa_agent = get_qa_agent(model=facts_model, provider="mistral")
    facts_agent = get_answer_facts_agent(provider="mistral", model=facts_model)

    questions = {}
    for qid in question_ids:
        question = texts[qid]
        passage = passage_map[qid]

        reference_answer = None
        try:
            qa_input = QuestionRequestInput(
                message=(
                    "Réponds à la question suivante en une ou deux phrases, "
                    "uniquement à partir du document. Question: " + question
                ),
                document=passage,
                num_questions=1,
            )
            qa_output = qa_agent.run(qa_input)
            qa_list = qa_output.QA_list
            if qa_list:
                reference_answer = qa_list[0].answer.strip()
        except Exception as e:
            logger.error("Génération de la réponse de référence %s échouée: %s", qid, e)
        if not reference_answer:
            logger.error("Pas de réponse de référence pour %s, question ignorée", qid)
            continue

        facts = []
        try:
            facts_output = facts_agent.run(
                FactExtractionInput(paragraph=reference_answer)
            )
            facts = [
                {"content": f.content, "importance": f.importance}
                for f in facts_output.facts
            ]
        except Exception as e:
            logger.error("Extraction des faits pour %s échouée: %s", qid, e)

        questions[qid] = {"answer": reference_answer, "facts": facts}
        logger.info(
            "%s: %d faits extraits | réponse: %s",
            qid, len(facts), reference_answer[:80],
        )

    with open(FACTS_FILE, "w", encoding="utf-8") as f:
        json.dump({"model": facts_model, "questions": questions}, f, ensure_ascii=False, indent=2)
    logger.info("Faits de réponse écrits dans %s", FACTS_FILE)
    return questions


def evaluate_answer(agent, question: str, expected_answers: list, user_answer: str):
    """Appelle l'évaluateur; renvoie le score (1-10) ou -1 en cas d'erreur."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = agent.run(
                EvaluateRequestInput(
                    question=question,
                    expected_answers=expected_answers,
                    user_answer=user_answer,
                )
            )
            score = int(result.score)
            if 1 <= score <= 10:
                return score
            logger.warning("Score hors bornes (%s), ignoré", score)
        except Exception as e:
            logger.warning(
                "Erreur LLM (tentative %d/%d): %s", attempt + 1, MAX_RETRIES + 1, e
            )
            time.sleep(2)
    return -1


def main():
    parser = argparse.ArgumentParser(description="Évaluation du dataset ROARs")
    parser.add_argument(
        "--facts-model",
        default=FACTS_MODEL_DEFAULT,
        help="Modèle pour générer les réponses de référence et les faits",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre maximum de lignes à traiter (pour test)",
    )
    args = parser.parse_args()

    if not DATA_FILE.exists() or not TEXTS_FILE.exists():
        logger.error("Fichiers ROARs introuvables dans %s", ROARS_DIR)
        sys.exit(1)

    questions = build_reference_answers(args.facts_model)
    texts = load_texts()

    with open(DATA_FILE, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    score_columns = [
        f"{mode}_{short}"
        for short in EVALUATION_MODELS
        for mode in ("score_simple", "score_faits")
    ]
    for col in score_columns:
        if col not in fieldnames:
            fieldnames.append(col)

    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, encoding="utf-8-sig", newline="") as f:
            done = {
                (r["student"], r["question_id"]): r
                for r in csv.DictReader(f)
            }
        for row in rows:
            key = (row["student"], row["question_id"])
            if key in done:
                for col in score_columns:
                    if done[key].get(col, "") != "":
                        row[col] = done[key][col]

    agents = {
        short: get_evaluator_agent(model=model, provider="mistral")
        for short, model in EVALUATION_MODELS.items()
    }

    processed = 0
    for i, row in enumerate(rows, start=1):
        pending = [
            col
            for col in score_columns
            if row.get(col, "") in ("", "-1")
        ]
        if not pending:
            continue
        if args.limit is not None and processed >= args.limit:
            break
        processed += 1

        qid = row["question_id"]
        if qid not in questions:
            logger.error("[%d] Pas de faits pour %s, scores à -1", i, qid)
            for col in score_columns:
                row[col] = "-1"
            continue

        question = texts.get(qid, row["question_id"])
        reference = questions[qid]["answer"]
        facts = [f["content"] for f in questions[qid]["facts"]]
        user_answer = (row.get("student_answer") or "").strip()

        for col in pending:
            short = col.rsplit("_", 1)[1]
            if short not in agents:
                continue
            if col.startswith("score_simple"):
                expected = [reference]
            else:
                expected = facts if facts else [reference]
            row[col] = str(
                evaluate_answer(agents[short], question, expected, user_answer)
            )

        with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

        logger.info(
            "[%d/%d] %s %s: " + ", ".join("%s=%%s" % c for c in score_columns),
            i, len(rows), row["student"], qid,
            *[row.get(c, "") for c in score_columns],
        )

    logger.info(
        "Terminé: %d lignes traitées. Résultats dans %s", processed, OUTPUT_FILE
    )


if __name__ == "__main__":
    main()
