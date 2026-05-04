import os
from summariser import Summariser
from helper import extract_text_from_pdf
from agents.token_monitor import monitor_agent_call, print_token_info
from agents.summariser_agent import ChunkSummaryRequestInput, MergeSummariesRequestInput

DOCUMENT_ID = "dbd5f14a9e6545880b0cd505583ea7d1fe1e8b3d.pdf"
FOLDER = r"C:\Users\xenyi\Documents\Ressources-Pro\Thèse\M3C-documents"


def main():
    """
    Version modifiée de la fonction main qui ajoute le suivi des tokens.
    
    Cette approche utilise un wrapper autour de la classe Summariser existante
    pour ajouter le suivi des tokens sans modifier la classe elle-même.
    """
    
    # Initialiser le summariser normal
    summariser = Summariser("mistral-large-latest")
    
    # Variables pour suivre les tokens globaux
    total_input_tokens = 0
    total_output_tokens = 0
    total_calls = 0
    
    # Remplacer temporairement les méthodes des agents par des versions avec surveillance
    original_summariser_run = summariser.summariser.run
    original_merger_run = summariser.merger.run
    original_merger_with_context_run = summariser.merger_with_context.run
    
    def summariser_run_with_tokens(user_input):
        """Version avec surveillance des tokens pour le summariser."""
        nonlocal total_input_tokens, total_output_tokens, total_calls
        response, input_tokens, output_tokens = monitor_agent_call(
            agent=summariser.summariser,
            user_input=user_input
        )
        total_input_tokens += input_tokens.total
        total_output_tokens += output_tokens
        total_calls += 1
        print(f"  [TOKENS] Summariser: Entrée={input_tokens.total}, Sortie={output_tokens}")
        return response
    
    def merger_run_with_tokens(user_input):
        """Version avec surveillance des tokens pour le merger."""
        nonlocal total_input_tokens, total_output_tokens, total_calls
        response, input_tokens, output_tokens = monitor_agent_call(
            agent=summariser.merger,
            user_input=user_input
        )
        total_input_tokens += input_tokens.total
        total_output_tokens += output_tokens
        total_calls += 1
        print(f"  [TOKENS] Merger: Entrée={input_tokens.total}, Sortie={output_tokens}")
        return response
    
    def merger_with_context_run_with_tokens(user_input):
        """Version avec surveillance des tokens pour le merger avec contexte."""
        nonlocal total_input_tokens, total_output_tokens, total_calls
        response, input_tokens, output_tokens = monitor_agent_call(
            agent=summariser.merger_with_context,
            user_input=user_input
        )
        total_input_tokens += input_tokens.total
        total_output_tokens += output_tokens
        total_calls += 1
        print(f"  [TOKENS] Merger+Context: Entrée={input_tokens.total}, Sortie={output_tokens}")
        return response
    
    # Remplacer les méthodes
    summariser.summariser.run = summariser_run_with_tokens
    summariser.merger.run = merger_run_with_tokens
    summariser.merger_with_context.run = merger_with_context_run_with_tokens
    
    try:
        print("Test de résumé avec surveillance des tokens (approche wrapper)")
        print("=" * 60)
        
        # Appeler la méthode originale qui utilisera maintenant nos versions avec surveillance
        summary = summariser.summarise(DOCUMENT_ID, os.path.join(FOLDER, DOCUMENT_ID))
        
        # Afficher le résumé final
        print(f"\nRésumé final:")
        print(f"-" * 40)
        print(summary)
        print(f"-" * 40)
        
        # Afficher le résumé de l'utilisation des tokens
        print(f"\n{'='*60}")
        print(f"RÉSUMÉ DE L'UTILISATION DES TOKENS")
        print(f"{'='*60}")
        print(f"Modèle utilisé: {summariser.model}")
        print(f"Nombre total d'appels aux agents: {total_calls}")
        print(f"Tokens d'entrée totaux: {total_input_tokens}")
        print(f"Tokens de sortie totaux: {total_output_tokens}")
        print(f"Tokens totaux (entrée + sortie): {total_input_tokens + total_output_tokens}")
        if total_input_tokens > 0:
            print(f"Ratio sortie/entrée: {(total_output_tokens / total_input_tokens):.2f}")
        print(f"{'='*60}")
        
    finally:
        # Restaurer les méthodes originales
        summariser.summariser.run = original_summariser_run
        summariser.merger.run = original_merger_run
        summariser.merger_with_context.run = original_merger_with_context_run


if __name__ == "__main__":
    main()