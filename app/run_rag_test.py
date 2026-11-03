#!/usr/bin/env python3
"""
Script pour tester les questions RAG sur un document spécifique avec session.
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:8000"
DOCUMENT_ID = "8a672d2ae6f2abfa4434e0f4145a9aa77bbc6d56"
MODEL = "mistral-large-4"
QUESTIONS_FILE = "test-questions-rag.txt"
RESPONSES_FILE = "reponses-test-rag-8a672d2a.txt"
SESSION_FILE = "session-8a672d2a.csv"

# Paramètres par défaut pour les requêtes
DEFAULT_PARAMS = {
    "k": 3,
    "use_rag": True,
    "use_reranking": False,
    "include_quantitative": False,
    "use_ontology_enrichment": False,
    "rag_monodocument_id": DOCUMENT_ID,
}


def create_session():
    """Créer une nouvelle session RAG pour le document via /api/sessions/init/{document_id}."""
    url = f"{BASE_URL}/api/sessions/rag/init/{DOCUMENT_ID}"
    payload = {"premade_session": True}
    response = requests.get(url, json=payload)
    response.raise_for_status()
    return response.json()


def read_questions(filename):
    """Lire les questions depuis un fichier texte."""
    with open(filename, "r", encoding="utf-8") as f:
        questions = [line.strip() for line in f if line.strip()]
    return questions


def ask_question(question, session_id):
    """Envoyer une question à l'API RAG monodocument."""
    url = f"{BASE_URL}/api/query/single-doc-rag"
    payload = {
        **DEFAULT_PARAMS,
        "question": question,
        "models": [MODEL],
        "session_id": session_id,
    }
    
    print(f"  Question: {question}")
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()


def export_session(session_id):
    """Exporter la session via /api/sessions/export/{session_id}."""
    url = f"{BASE_URL}/api/sessions/rag/export/{session_id}"
    response = requests.get(url)
    response.raise_for_status()
    return response.text


def format_response(question, data, question_num):
    """Formater une réponse pour l'affichage/sauvegarde."""
    answer = data.get("answer", "")
    sources = data.get("sources", [])
    total_time = data.get("total_time", 0)
    metadata = data.get("metadata", {})
    model = metadata.get("model", MODEL)
    
    formatted = f"=== Question {question_num} ===\n"
    formatted += f"Q: {question}\n"
    formatted += f"A: {answer}\n"
    formatted += f"Model: {model}\n"
    formatted += f"Time: {total_time}s\n"
    formatted += "Sources:\n"
    for i, source in enumerate(sources or [], 1):
        formatted += f"  {i}. {source}\n"
    formatted += "\n"
    return formatted


def main():
    print("Démarrage du test RAG monodocument...")
    print(f"Document: {DOCUMENT_ID}")
    print(f"Modèle: {MODEL}")
    
    # Étape 1: Créer une session
    print("\n1. Création de la session...")
    session_id = create_session()
    print(f"   Session créée: {session_id}")
    
    # Étape 2: Lire les questions
    print("\n2. Lecture des questions...")
    questions = read_questions(QUESTIONS_FILE)
    print(f"   {len(questions)} questions chargées")
    
    # Étape 3: Poser chaque question
    print("\n3. Envoi des questions...")
    all_responses = []
    
    for i, question in enumerate(questions, 1):
        print(f"\n  [{i}/{len(questions)}]")
        try:
            data = ask_question(question, session_id)
            all_responses.append(format_response(question, data, i))
            time.sleep(1)
        except Exception as e:
            print(f"    Erreur: {e}")
            all_responses.append(f"=== Question {i} ===\nQ: {question}\nA: [ERREUR: {str(e)}]\n\n")
    
    # Étape 4: Sauvegarder les réponses
    print("\n4. Sauvegarde des réponses...")
    with open(RESPONSES_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(all_responses))
    print(f"   Réponses sauvegardées dans {RESPONSES_FILE}")
    
    # Étape 5: Exporter la session
    print("\n5. Export de la session...")
    session_data = export_session(session_id)
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        f.write(session_data)
    print(f"   Session exportée dans {SESSION_FILE} (format CSV)")
    
    print("\nTest terminé!")


if __name__ == "__main__":
    main()
