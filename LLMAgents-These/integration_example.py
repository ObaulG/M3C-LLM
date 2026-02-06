# integration_example.py
"""
Exemple concret d'intégration du moniteur de tokens dans le code existant.

Ce fichier montre comment modifier une fonction existante pour ajouter
du moniteur de tokens sans changer radicalement la structure du code.
"""

from agents.qa_agent import get_qa_agent, QuestionRequestInput
from agents.token_monitor import monitor_agent_call, print_token_info
from typing import Dict, Any


class SessionManager:
    """Classe simulée pour gérer les sessions (similaire à celle utilisée dans api_server.py)"""
    
    def __init__(self):
        self.sessions = {}
        
    def create_session(self, session_id: str, document_id: str):
        """Crée une nouvelle session."""
        self.sessions[session_id] = {
            "document_id": document_id,
            "questions": []
        }
        
    def add_questions(self, session_id: str, questions: list):
        """Ajoute des questions à une session."""
        if session_id in self.sessions:
            self.sessions[session_id]["questions"] = questions


# Initialiser le gestionnaire de sessions
session_manager = SessionManager()


def init_session_original(document_id: str) -> Dict[str, Any]:
    """
    Version ORIGINALE sans surveillance des tokens.
    
    Cette fonction est similaire à celle dans api_server.py.
    """
    # Générer les questions/réponses pour le document
    qa_agent = get_qa_agent()
    response = qa_agent.run({"message": "Génère 3 questions.", "document": document_id})
    
    # Créer une nouvelle session
    session_id = "test_session_123"
    session_manager.create_session(session_id, document_id)
    session_manager.add_questions(session_id, response.questions_answers)
    
    return {
        "session_id": session_id,
        "document_id": document_id,
        "questions": response.questions_answers,
    }


def init_session_with_monitoring(document_id: str) -> Dict[str, Any]:
    """
    Version MODIFIÉE avec surveillance des tokens.
    
    Cette fonction montre comment intégrer le moniteur de tokens
    dans le code existant.
    """
    # Initialiser l'agent QA
    qa_agent = get_qa_agent()
    
    # Créer l'entrée utilisateur
    user_input = QuestionRequestInput(
        message="Génère 3 questions.",
        document=document_id
    )
    
    # Appeler l'agent avec surveillance des tokens
    response, input_tokens, output_tokens = monitor_agent_call(
        agent=qa_agent,
        user_input=user_input
    )
    
    # Afficher les informations de tokens (optionnel - peut être désactivé en production)
    print_token_info(input_tokens, output_tokens, "run")
    
    # Créer une nouvelle session
    session_id = "test_session_123"
    session_manager.create_session(session_id, document_id)
    session_manager.add_questions(session_id, response.questions_answers)
    
    # Retourner les informations de tokens (optionnel)
    return {
        "session_id": session_id,
        "document_id": document_id,
        "questions": response.questions_answers,
        "token_usage": {
            "input_tokens": input_tokens.total,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens.total + output_tokens,
            "model": input_tokens.model,
            "system_tokens": input_tokens.system_prompt,
            "tools_tokens": input_tokens.tools
        }
    }


def init_session_with_logging(document_id: str) -> Dict[str, Any]:
    """
    Version AVEC JOURNALISATION des tokens.
    
    Cette version montre comment enregistrer les informations de tokens
    dans des logs pour le suivi et l'analyse.
    """
    import logging
    from datetime import datetime
    
    # Configurer le logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("token_monitor")
    
    # Initialiser l'agent QA
    qa_agent = get_qa_agent()
    
    # Créer l'entrée utilisateur
    user_input = QuestionRequestInput(
        message="Génère 3 questions.",
        document=document_id
    )
    
    # Appeler l'agent avec surveillance des tokens
    response, input_tokens, output_tokens = monitor_agent_call(
        agent=qa_agent,
        user_input=user_input
    )
    
    # Journaliser les informations de tokens
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "model": input_tokens.model,
        "input_tokens": input_tokens.total,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens.total + output_tokens,
        "system_tokens": input_tokens.system_prompt,
        "tools_tokens": input_tokens.tools,
        "document_id": document_id,
        "num_questions": len(response.questions_answers)
    }
    
    logger.info("Token usage logged: %s", log_data)
    
    # Créer une nouvelle session
    session_id = "test_session_123"
    session_manager.create_session(session_id, document_id)
    session_manager.add_questions(session_id, response.questions_answers)
    
    return {
        "session_id": session_id,
        "document_id": document_id,
        "questions": response.questions_answers,
        "token_usage": log_data
    }


def compare_approaches():
    """Compare les différentes approches."""
    document_id = "exemple_document_ai_123"
    
    print("=" * 80)
    print("COMPARAISON DES APPROCHES")
    print("=" * 80)
    
    print("\n1. APPROCHE ORIGINALE (sans surveillance)")
    print("-" * 40)
    try:
        result_original = init_session_original(document_id)
        print(f"[OK] Session creee: {result_original['session_id']}")
        print(f"[OK] Questions generees: {len(result_original['questions'])}")
        print(f"[INFO] Aucune information sur les tokens")
    except Exception as e:
        print(f"[ERREUR] Erreur: {e}")
    
    print("\n2. APPROCHE AVEC SURVEILLANCE DES TOKENS")
    print("-" * 40)
    try:
        result_monitored = init_session_with_monitoring(document_id)
        print(f"[OK] Session creee: {result_monitored['session_id']}")
        print(f"[OK] Questions generees: {len(result_monitored['questions'])}")
        print(f"[OK] Tokens d'entree: {result_monitored['token_usage']['input_tokens']}")
        print(f"[OK] Tokens de sortie: {result_monitored['token_usage']['output_tokens']}")
        print(f"[OK] Total: {result_monitored['token_usage']['total_tokens']}")
    except Exception as e:
        print(f"[ERREUR] Erreur: {e}")
    
    print("\n3. APPROCHE AVEC JOURNALISATION")
    print("-" * 40)
    try:
        result_logged = init_session_with_logging(document_id)
        print(f"[OK] Session creee: {result_logged['session_id']}")
        print(f"[OK] Questions generees: {len(result_logged['questions'])}")
        print(f"[OK] Informations journalisees (voir logs)")
        print(f"[OK] Tokens totaux: {result_logged['token_usage']['total_tokens']}")
    except Exception as e:
        print(f"[ERREUR] Erreur: {e}")
    
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print("Le moniteur de tokens peut être intégré de manière progressive:")
    print("1. Commencez par l'approche simple (affichage console)")
    print("2. Passez à la journalisation pour le suivi")
    print("3. Intégrez dans les API pour exposer les métriques aux clients")
    print("4. Utilisez les données pour optimiser et réduire les coûts")


def main():
    """Fonction principale."""
    try:
        compare_approaches()
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()