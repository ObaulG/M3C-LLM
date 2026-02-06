# token_monitor_example.py
"""
Exemple d'intégration du moniteur de tokens dans du code existant.

Ce fichier montre comment modifier les appels existants aux agents pour utiliser
du moniteur de tokens.
"""

from agents.qa_agent import get_qa_agent, QuestionRequestInput
from agents.token_monitor import monitor_agent_call, print_token_info

def generate_questions_with_token_monitoring(document_id: str, num_questions: int = 3):
    """
    Exemple de fonction modifiée pour utiliser le moniteur de tokens.
    
    Cette fonction est similaire à celle utilisée dans api_server.py mais avec
    l'ajout du moniteur de tokens.
    """
    # Initialiser l'agent QA
    qa_agent = get_qa_agent()
    
    # Créer l'entrée utilisateur
    user_input = QuestionRequestInput(
        message=f"Génère {num_questions} questions.",
        document=document_id
    )
    
    # Appeler l'agent avec surveillance des tokens
    response, input_tokens, output_tokens = monitor_agent_call(
        agent=qa_agent,
        user_input=user_input
        # method="run" est la valeur par défaut
    )
    
    # Afficher les informations de tokens (optionnel)
    print_token_info(input_tokens, output_tokens, "run")
    
    # Retourner la réponse et les informations de tokens
    return {
        "response": response,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens
    }

def generate_questions_original(document_id: str, num_questions: int = 3):
    """
    Version originale sans surveillance des tokens.
    
    Cette fonction montre comment le code était avant l'ajout du moniteur.
    """
    # Initialiser l'agent QA
    qa_agent = get_qa_agent()
    
    # Créer l'entrée utilisateur
    user_input = QuestionRequestInput(
        message=f"Génère {num_questions} questions.",
        document=document_id
    )
    
    # Appel original sans surveillance
    response = qa_agent.run(user_input)
    
    return response

def example_usage():
    """Exemple d'utilisation montrant la différence entre les deux approches."""
    document_id = "exemple_document_123"
    
    print("=== APPROCHE ORIGINALE (sans surveillance) ===")
    response_original = generate_questions_original(document_id)
    print(f"Nombre de questions générées: {len(response_original.questions_answers)}")
    print()
    
    print("=== APPROCHE AVEC SURVEILLANCE DES TOKENS ===")
    result_with_monitoring = generate_questions_with_token_monitoring(document_id)
    response = result_with_monitoring["response"]
    input_tokens = result_with_monitoring["input_tokens"]
    output_tokens = result_with_monitoring["output_tokens"]
    
    print(f"Nombre de questions générées: {len(response.questions_answers)}")
    print(f"Tokens d'entrée: {input_tokens.total}")
    print(f"Tokens de sortie: {output_tokens}")
    print(f"Total: {input_tokens.total + output_tokens}")

def main():
    """Fonction principale."""
    try:
        example_usage()
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()