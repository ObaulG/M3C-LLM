#!/usr/bin/env python3
"""Constitution du jeu de données qa_statements.

Pour chaque document demandé, pioche n questions/réponses existantes dans la
base de données, génère pour chaque réponse de référence la liste des
affirmations qui la constituent via un LLM, puis insère le tout dans
qa_statements.json.

Usage (depuis la racine du dépôt) :
    python -m app.qa_statements.build_dataset --documents 21 34 --num-questions 3
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database.database import get_db_connection, get_questions_by_document_id
from app.qa_statements.utils import (
    get_llm_client,
    init_json,
    pick_n_questions,
    save_json,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_statement_extraction_client(provider: str, model: Optional[str]):
    """Crée le client LLM utilisé pour extraire les affirmations d'une réponse."""
    return get_llm_client(provider, model)


async def extract_statements(
    client,
    model: str,
    answer_content: str,
) -> List[str]:
    """Demande au LLM la liste des affirmations qui constituent la réponse."""
    from pydantic import BaseModel

    class StatementsExtraction(BaseModel):
        """Liste des affirmations (propositions) contenues dans la réponse."""
        statements: List[str]

    extraction = client.chat.completions.create(
        model=model,
        response_model=StatementsExtraction,
        messages=[
            {
                "role": "user",
                "content": (
                    "Décompose la réponse suivante en la liste ordonnée des "
                    "affirmations (propositions) qu'elle contient. Chaque "
                    "affirmation doit être autonome, vérifiable et formulée "
                    "en français, sans commentaire ni interprétation.\n\n"
                    f"Réponse : {answer_content}"
                ),
            }
        ],
    )
    return extraction.statements


async def build_dataset(
    documents: List[int],
    num_questions: int,
    provider: str = "mistral",
    model: Optional[str] = None,
    seed: Optional[int] = None,
) -> Dict:
    """Point d'entrée principal : pioche les questions et génère les affirmations.

    Args:
        documents: liste des IDs de documents à traiter.
        num_questions: nombre de questions à piocher par document.
        provider: fournisseur LLM ("mistral" ou "ollama").
        model: nom du modèle LLM (défaut selon le fournisseur).
        seed: graine aléatoire pour un tirage reproductible.

    Returns:
        Le contenu final de qa_statements.json.
    """
    client = get_statement_extraction_client(provider, model)
    model_name = model or "mistral-medium"
    data = init_json(model_name)
    conn = await get_db_connection()
    try:
        for document_id in documents:
            logger.info(f"Document {document_id} : récupération des questions")
            questions = await get_questions_by_document_id(document_id, conn)
            if not questions:
                logger.warning(f"Document {document_id} : aucune question trouvée")
                data["documents"].setdefault(str(document_id), {"questions": []})
                continue

            picked = pick_n_questions(questions, num_questions, seed=seed)
            logger.info(
                f"Document {document_id} : {len(picked)} question(s) piochée(s) "
                f"sur {len(questions)}"
            )

            document_questions = []
            for question in picked:
                answers = []
                for answer in question.get("answers", []):
                    statements = await extract_statements(client, model_name, answer["content"])
                    answers.append({
                        "answer_id": answer["answer_id"],
                        "is_correct": answer["is_correct"],
                        "content": answer["content"],
                        "statements": statements,
                    })
                document_questions.append({
                    "question_id": question["question_id"],
                    "question_text": question["content"],
                    "answers": answers,
                })
                logger.info(
                    f"Document {document_id}, question {question['question_id']} : "
                    f"{len(answers)} réponse(s), affirmations générées"
                )

            data["documents"][str(document_id)] = {"questions": document_questions}
    finally:
        conn.close()

    save_json(data)
    logger.info(f"Données écrites dans qa_statements.json")
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Pioche n questions/réponses pour k documents et génère "
        "les affirmations de chaque réponse."
    )
    parser.add_argument(
        "--documents",
        type=int,
        nargs="+",
        required=True,
        help="IDs des documents à traiter",
    )
    parser.add_argument(
        "--num-questions",
        type=int,
        default=3,
        help="Nombre de questions à piocher par document (défaut : 3)",
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
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Graine aléatoire pour un tirage reproductible",
    )
    args = parser.parse_args()

    asyncio.run(
        build_dataset(
            documents=args.documents,
            num_questions=args.num_questions,
            provider=args.provider,
            model=args.model,
            seed=args.seed,
        )
    )


if __name__ == "__main__":
    main()
