import os
import json
from summariser import Summariser
from helper import extract_text_from_pdf, split_text_in_chunks
from agents.token_monitor import monitor_agent_call, print_token_info
from agents.summariser_agent import ChunkSummaryRequestInput, MergeSummariesRequestInput

DOCUMENT_ID = "38c34c19a42af9abdec31f62cc5353abdc4e6f25.pdf"
FOLDER = r"C:\Users\xenyi\Documents\Ressources-Pro\Thèse\M3C-documents"

class TokenMonitoringSummariser(Summariser):
    """
    Classe étendue qui ajoute le suivi des tokens au processus de résumé.
    
    Cette classe hérite de Summariser et ajoute la surveillance des tokens
    pour chaque appel aux agents.
    """
    
    def __init__(self, model: str = "mistral-medium"):
        super().__init__(model=model)
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0
        
    def reset_token_counters(self):
        """Réinitialise les compteurs de tokens."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0
    
    def summarise_with_token_monitoring(self, document_id: str, document_path: str):
        """
        Version modifiée de la méthode summarise qui suit l'utilisation des tokens.
        
        Cette méthode utilise le moniteur de tokens pour suivre chaque appel
        aux agents et accumule les statistiques globales.
        """
        # Réinitialiser les compteurs
        self.reset_token_counters()
        
        document_content = extract_text_from_pdf(document_path)
        chunks = split_text_in_chunks(document_content, self.chunk_size)
        depth = 0
        print(f"Début du résumé avec surveillance des tokens")
        
        # Résumés initiaux des chunks
        chunk_summaries = []
        
        # Récupérer la progression déjà effectuée
        output_file = "../progress_summaries.json"
        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as f:
                progress_data = json.load(f)
                if progress_data.get(document_id):
                    chunk_summaries = progress_data[document_id]["chunk_summaries"]
                    print(f"Reprise de la progression à partir du chunk {len(chunk_summaries)}.")
        
        summary_start_index = len(chunk_summaries)
        
        # Résumer chaque chunk avec surveillance des tokens
        for i, chunk in enumerate(chunks):
            if i < summary_start_index:
                continue
                
            print(f"Résumé du chunk {i + 1}/{len(chunks)} avec surveillance des tokens...")
            
            # Utiliser le moniteur de tokens pour l'appel au summariser
            user_input = ChunkSummaryRequestInput(chunk_text=chunk)
            response, input_tokens, output_tokens = monitor_agent_call(
                agent=self.summariser,
                user_input=user_input
            )
            
            # Mettre à jour les compteurs globaux
            self.total_input_tokens += input_tokens.total
            self.total_output_tokens += output_tokens
            self.call_count += 1
            
            # Afficher les informations pour ce chunk (optionnel)
            print(f"  Chunk {i+1}: Entrée={input_tokens.total} tokens, Sortie={output_tokens} tokens")
            
            # Réinitialiser l'historique comme dans la méthode originale
            self.summariser.reset_history()
            
            chunk_summaries.append(response.summary)
            print(f"Chunk {i + 1}/{len(chunks)} résumé.")
            
            self.save_progress(chunk_summaries, document_id, output_file)
        
        # Fusionner les résumés avec surveillance des tokens
        while len(chunk_summaries) > 1:
            new_summaries = []
            
            # Calculer le nombre de tokens comme dans la méthode originale
            nb_tokens = 0
            nb_summaries = 0
            index_start = 0
            index_end = 0
            
            while index_end < len(chunk_summaries):
                while nb_tokens < 0.8 * self.window_size and index_end < len(chunk_summaries):
                    nb_tokens += self.token_counter.count_text(self.model, chunk_summaries[index_end])
                    index_end += 1
                
                # Résumer avec surveillance des tokens
                print(f"Fusion des résumés {index_start+1} à {index_end} avec surveillance des tokens...")
                
                if index_start == 0:
                    # Premier résumé sans contexte
                    user_input = MergeSummariesRequestInput(summaries=chunk_summaries[:index_end])
                    response, input_tokens, output_tokens = monitor_agent_call(
                        agent=self.merger,
                        user_input=user_input
                    )
                else:
                    # Résumés suivants avec contexte
                    context = [summary.merged_summary for summary in new_summaries[nb_summaries-1]]
                    user_input = MergeSummariesRequestInput(
                        summaries=chunk_summaries[index_start:index_end],
                        context=context
                    )
                    response, input_tokens, output_tokens = monitor_agent_call(
                        agent=self.merger_with_context,
                        user_input=user_input
                    )
                
                # Mettre à jour les compteurs globaux
                self.total_input_tokens += input_tokens.total
                self.total_output_tokens += output_tokens
                self.call_count += 1
                
                # Afficher les informations pour cette fusion (optionnel)
                print(f"  Fusion {nb_summaries+1}: Entrée={input_tokens.total} tokens, Sortie={output_tokens} tokens")
                
                nb_summaries += 1
                new_summaries.append(response)
            
            depth += 1
            chunk_summaries.clear()
            chunk_summaries.extend(new_summaries)
            new_summaries.clear()
        
        return chunk_summaries[0]
    
    def print_token_summary(self):
        """Affiche un résumé de l'utilisation des tokens."""
        print(f"\n{'='*60}")
        print(f"RÉSUMÉ DE L'UTILISATION DES TOKENS")
        print(f"{'='*60}")
        print(f"Modèle utilisé: {self.model}")
        print(f"Nombre total d'appels aux agents: {self.call_count}")
        print(f"Tokens d'entrée totaux: {self.total_input_tokens}")
        print(f"Tokens de sortie totaux: {self.total_output_tokens}")
        print(f"Tokens totaux (entrée + sortie): {self.total_input_tokens + self.total_output_tokens}")
        print(f"Ratio sortie/entrée: {(self.total_output_tokens / self.total_input_tokens):.2f}")
        print(f"{'='*60}")


def main():
    """Fonction principale avec surveillance des tokens."""
    print("Test de résumé avec surveillance des tokens")
    print("=" * 60)
    
    # Utiliser la classe étendue avec surveillance des tokens
    summariser = TokenMonitoringSummariser("mistral-medium-latest")
    
    # Résumer le document avec surveillance des tokens
    summary = summariser.summarise_with_token_monitoring(DOCUMENT_ID, os.path.join(FOLDER, DOCUMENT_ID))
    
    # Afficher le résumé final
    print(f"\nRésumé final:")
    print(f"-" * 40)
    print(summary)
    print(f"-" * 40)
    
    # Afficher le résumé de l'utilisation des tokens
    summariser.print_token_summary()


if __name__ == "__main__":
    main()