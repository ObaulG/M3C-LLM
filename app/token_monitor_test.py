# token_monitor_test.py
"""
Test pour démontrer l'utilisation du moniteur de tokens avec les agents AtomicAgent.

Ce script montre comment utiliser le moniteur de tokens pour obtenir des informations
détaillées sur l'utilisation des tokens lors des appels aux agents.
"""

import asyncio
from agents.qa_agent import get_qa_agent, QuestionRequestInput
from agents.token_monitor import monitor_agent_call, print_token_info

def test_token_monitoring():
    """Teste le moniteur de tokens avec un agent QA."""
    print("Test du moniteur de tokens avec AtomicAgent")
    print("=" * 60)
    
    # Initialiser l'agent QA
    qa_agent = get_qa_agent(model="mistral-medium")
    
    # Créer une entrée utilisateur
    user_input = QuestionRequestInput(
        message="Génère 3 questions sur l'intelligence artificielle.",
        document="L'intelligence artificielle est une technologie qui permet aux machines d'apprendre et de prendre des décisions."
    )
    
    print("Appel de l'agent avec surveillance des tokens...")
    
    # Appeler l'agent avec surveillance des tokens
    response, input_tokens, output_tokens = monitor_agent_call(
        agent=qa_agent, 
        user_input=user_input
        # method="run" est la valeur par défaut
    )
    
    # Afficher les informations de tokens
    print_token_info(input_tokens, output_tokens, "run")
    
    # Afficher la réponse
    print("Réponse de l'agent:")
    print(f"Nombre de questions générées: {len(response.questions_answers)}")
    for i, qa in enumerate(response.questions_answers):
        print(f"Q{i+1}: {qa.question_text}")
        print(f"A{i+1}: {qa.answer_text}")
        print()
    
    return response, input_tokens, output_tokens

async def test_async_token_monitoring():
    """Teste le moniteur de tokens avec un appel asynchrone."""
    print("Test du moniteur de tokens avec appel asynchrone")
    print("=" * 60)
    
    # Note: Pour les appels asynchrones, nous devons utiliser un client async
    # et la méthode run_async. Cependant, cela nécessite une configuration
    # spécifique que nous n'avons pas dans cet exemple.
    
    print("Les appels asynchrones nécessitent un client async Instructor.")
    print("Voir la documentation pour plus d'informations.")

def main():
    """Fonction principale pour exécuter les tests."""
    try:
        # Test synchrone
        response, input_tokens, output_tokens = test_token_monitoring()
        
        # Test asynchrone (commenté car nécessite une configuration spécifique)
        # asyncio.run(test_async_token_monitoring())
        
        print("Test terminé avec succès!")
        
    except Exception as e:
        print(f"Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()