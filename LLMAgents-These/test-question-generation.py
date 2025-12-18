import csv
import json
import os
import pickle
import re

import faiss
from httpx import HTTPStatusError
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import create_retriever_tool
from langchain_mistralai import MistralAIEmbeddings, ChatMistralAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

from api_check import check_api_key_usage

FAISS_DB_PATH = "faiss_index.bin"
FAISS_DOCSTORE_PATH = "index_to_docstore_id.pkl"
OUTPUT_CSV: str = "questions_qa"
# voir https://admin.mistral.ai/plateforme/limits
DEFAULT_MODEL = "mistral-small-2501"

def clean_json_output(raw: str) -> str:
    """
    Nettoie un JSON renvoyé par le modèle en supprimant :
    - les fences markdown ``` et ```json
    - tout texte avant le premier '{'
    - tout texte après le dernier '}'
    """
    s = raw.strip()

    # 1. Supprimer les ```xxx et ```
    s = re.sub(r"^```[a-zA-Z]*", "", s)           # au début
    s = re.sub(r"```$", "", s)                   # à la fin
    s = s.replace("```json", "").replace("```", "")

    # 2. Garder à partir de la première accolade ouvrante
    if "{" in s:
        s = s[s.index("{"):]
    # 3. Garder jusqu'à la dernière accolade fermante
    if "}" in s:
        s = s[:s.rindex("}")+1]

    return s.strip()
def generate_qa_for_chunk(lm: BaseChatModel,
                          text: str,
                          n_questions: int = 3) -> list[tuple[str, str]]:
    """
    Génère n_questions paires (question, réponse) à partir d'un chunk de texte.
    Retourne une liste de tuples (question, réponse).
    """
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

Ne mets aucun texte avant ou après le JSON.
"""
    response = lm.invoke([HumanMessage(content=prompt)])
    raw = response.content.strip()
    print(f"Response: {raw}")
    # Tentative de parsing JSON strict
    try:
        data = json.loads(clean_json_output(raw))
        qas = data.get("qas", [])
        print("qas ok")
        result: list[tuple[str, str]] = []

        for qa in qas:
            q = qa.get("question", "").strip()
            a = qa.get("answer", "").strip()
            print("q a ok")
            if q and a:
                result.append((q, a))
        return result

    except Exception as e:
        # Mode dégradé : si le JSON est "cassé", on essaie de récupérer quelque chose
        print("Avertissement : échec du parsing JSON, fallback texte brut.", e)
        # Fallback très simple : pas de structure fiable, donc on renvoie une liste vide
        # (tu peux ici implémenter un split manuel sur les lignes si tu veux tenter de récupérer)
        return []

if __name__ == '__main__':
    if not os.path.exists(FAISS_DB_PATH):
        print("FAISS database not found.")
        raise SystemExit(1)


    index = faiss.read_index("faiss_index.bin")

    # Load the index_to_docstore_id mapping
    with open("index_to_docstore_id.pkl", "rb") as f:
        index_to_docstore_id = pickle.load(f)

    embedder = MistralAIEmbeddings(model="mistral-embed")

    vector_store = FAISS(
        embedding_function=embedder,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id=index_to_docstore_id,
    )

    # dbd5f14a9e6545880b0cd505583ea7d1fe1e8b3d.pdf
    # page 35
    document_path = "documents\\test-m3c"+"\\"+"dbd5f14a9e6545880b0cd505583ea7d1fe1e8b3d.pdf"

    loader = PyPDFLoader(document_path)
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    texts = text_splitter.split_documents(documents)

    llm = ChatMistralAI(
        model=DEFAULT_MODEL,
        temperature=0.7,
        max_retries=2,
        mistral_api_key=os.getenv("MISTRAL_API_KEY"),
        # other params...
    )

    check_api_key_usage(os.getenv("MISTRAL_API_KEY"))

    rows = []
    # we generate questions from chunks of the document
    for i, doc in enumerate(texts):
        chunk_id = f"{i}"
        chunk_text = doc.page_content

        print(f"Generating QA for chunk {chunk_id}...")
        # Génération des paires Q/R pour ce chunk
        try:
            qas = generate_qa_for_chunk(
                lm= llm,
                text=chunk_text,
                n_questions=2
            )
        except HTTPStatusError as e:
            print("ERREUR LLM")
            print("Message :", str(e))
            print("Arrêt immédiat du traitement des chunks.")
            break

        except Exception as e:
            print("Erreur inattendue lors de l'appel au modèle :", e)
            break

        if not qas:
            continue  # rien de récupérable, on passe au chunk suivant

        for q_idx, (question, answer) in enumerate(qas):
            rows.append({
                "chunk_index": i,
                "chunk_id": chunk_id,
                "question_index": q_idx,
                "question": question,
                "answer": answer,
            })

    fieldnames = [
        "chunk_index",
        "chunk_id",
        "question_index",
        "question",
        "answer",
        # "chunk_text",
    ]

    with open(f"{OUTPUT_CSV}_{DEFAULT_MODEL}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV écrit dans {OUTPUT_CSV}_{DEFAULT_MODEL} avec {len(rows)} lignes.")