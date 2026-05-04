import json
import os
import re
import psycopg2
from typing import List, Tuple
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_mistralai import ChatMistralAI

import database
# Configuration de la base de données
DB_CONFIG = {
    "host": "localhost",
    "dbname": "mediationllm",
    "user": "postgres",
    "password": "postgres",
}

# Modèle par défaut
DEFAULT_MODEL = "mistral-small-2501"

def clean_json_output(raw: str) -> str:
    """Nettoie la sortie JSON du modèle."""
    s = raw.strip()
    s = re.sub(r"^```[a-zA-Z]*", "", s)
    s = re.sub(r"```$", "", s)
    s = s.replace("```json", "").replace("```", "")
    if "{" in s:
        s = s[s.index("{"):]
    if "}" in s:
        s = s[:s.rindex("}")+1]
    return s.strip()

def generate_qa_for_chunk(lm: BaseChatModel, text: str, n_questions: int = 3) -> List[Tuple[str, str]]:
    """Génère des paires (question, réponse) pour un chunk de texte."""
    prompt = f"""
Tu es un assistant pédagogique spécialisé dans la compréhension de textes.
À partir du texte suivant, génère exactement {n_questions} questions en français,
accompagnées chacune de leur réponse courte, basée uniquement sur le texte.

Texte :
\"\"\"{text}\"\"\"

Contraintes importantes :
- Les questions doivent être compréhensives (pas triviales, pas hors sujet).
- Les réponses doivent être directement justifiées par le texte.
- Si une information n'est pas clairement présente, ne l'invente pas : adapte la question.
- Les questions et réponses doivent être en français.

FORMAT DE SORTIE STRICT :
Réponds UNIQUEMENT avec un JSON valide de la forme :

{{
  "qas": [
    {{
      "question": "…",
      "answer": "…"
    }},
    {{
      "question": "…",
      "answer": "…"
    }}
  ]
}}
"""
    response = lm.invoke([HumanMessage(content=prompt)])
    raw = response.content.strip()
    print(f"Response: {raw}")
    try:
        data = json.loads(clean_json_output(raw))
        qas = data.get("qas", [])
        result = []
        for qa in qas:
            q = qa.get("question", "").strip()
            a = qa.get("answer", "").strip()
            if q and a:
                result.append((q, a))
        return result
    except Exception as e:
        print("Avertissement : échec du parsing JSON.", e)
        return []


if __name__ == '__main__':
    # Connexion à la base de données
    conn = psycopg2.connect(**DB_CONFIG)

    # ID du document à traiter
    document_id = "dbd5f14a9e6545880b0cd505583ea7d1fe1e8b3d"

    # Récupérer les chunks du document
    chunks = database.get_chunks_for_document(document_id, conn)
    if not chunks:
        print(f"Aucun chunk trouvé pour le document {document_id}.")
        exit(1)

    # Initialiser le modèle
    llm = ChatMistralAI(
        model=DEFAULT_MODEL,
        temperature=0.7,
        max_retries=2,
        mistral_api_key=os.getenv("MISTRAL_API_KEY"),
    )

    # Générer et sauvegarder les questions pour chaque chunk
    for chunk_id, chunk_text in chunks:
        print(f"Génération de questions pour le chunk {chunk_id}...")
        qas = generate_qa_for_chunk(llm, chunk_text, n_questions=2)
        if not qas:
            print(f"Aucune question générée pour le chunk {chunk_id}.")
            continue

        for question, answer in qas:
            database.save_question_to_db(question, answer, chunk_id, conn)
            print(f"Question sauvegardée : {question[:50]}...")

    print("Génération et sauvegarde des questions terminées.")
    conn.close()
