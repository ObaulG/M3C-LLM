import datetime
import json
import os

from atomic_agents.utils import token_counter

from agents.mistral_client import get_mistral_client
from helper import extract_text_from_pdf, split_text_in_chunks
from agents.summariser_agent import *

class Summariser():
    """
    Classe réalisant un résumé d'un document long en suivant une logique hiérarchique :
    - on découpe le document en chunks de taille donnée.
    - Pour chaque chunk, on appelle un LLM prévu pour générer un résumé de cette partie.

    """
    def __init__(self,
                 model: str = "mistral-medium",
                 window_size: int = 120000,
                 max_chunk_size: int = 1000,
                 max_summary_len: int = 1000,
                 word_per_token_ratio: float = 0.7):

        self.chunk_size = max_chunk_size
        self.model = model
        self.window_size = window_size
        self.max_summary_len = max_summary_len
        self.word_per_token_ratio = word_per_token_ratio
        self.client = get_mistral_client()
        self.summariser = get_chunk_summariser_agent(model)
        self.merger = get_summaries_merger_agent(model)
        self.merger_with_context = get_context_summaries_merger_agent(model)
        self.artifact_remover = get_artifact_removal_prompt_generator(model)

        self.token_counter = token_counter.get_token_counter()

    def summarise(self, document_id: str, document_path: str):

        #print(f"hello: {self.token_counter.count_text(self.model, "hello")}")
        document_content = extract_text_from_pdf(document_path)
        chunks = split_text_in_chunks(document_content, self.chunk_size)
        depth = 0
        print(f"Début du résumé")
        # initial summaries
        chunk_summaries = []

        # retrieve the progress already done
        output_file = "../progress_summaries.json"
        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as f:
                progress_data = json.load(f)
                if progress_data.get(document_id):
                    chunk_summaries = progress_data[document_id]["chunk_summaries"]
                    print(f"Reprise de la progression à partir du chunk {len(chunk_summaries)}.")
        summary_start_index = len(chunk_summaries)
        for i, chunk in enumerate(chunks):
            if i < summary_start_index:
                continue
            summary = self.summariser.run(ChunkSummaryRequestInput(chunk_text=chunk))
            # the framework keeps the history, so we need to clear it after
            # each call
            self.summariser.reset_history()
            chunk_summaries.append(summary.summary)
            print(f"Chunk {i + 1}/{len(chunks)} résumé.")

            self.save_progress(chunk_summaries, document_id, output_file)
        # merges summaries : the first one has no context, next have given context
        while len(chunk_summaries) > 1:
            new_summaries = []

            # the number of summaries thrown into the llm should fill the context window
            nb_tokens = 0
            nb_summaries = 0
            index_start = 0
            index_end = 0
            while index_end < len(chunk_summaries):
                while nb_tokens < 0.8 * self.window_size and index_end < len(chunk_summaries):
                    nb_tokens += self.token_counter.count_text(self.model, chunk_summaries[index_end])
                    index_end += 1

                # the first summary has not previous context
                if index_start == 0:
                    summary = self.merger.run(MergeSummariesRequestInput(summaries=chunk_summaries[:index_end]))
                else:
                    summary = self.merger_with_context.run(MergeSummariesRequestInput(summaries=chunk_summaries[index_start:index_end],
                                                                                      context=[summary.merged_summary for summary in new_summaries[nb_summaries-1]]))
                nb_summaries += 1
                new_summaries.append(summary)

            depth += 1
            chunk_summaries.clear()
            chunk_summaries.extend(new_summaries)
            new_summaries.clear()
        return chunk_summaries[0]

    def save_progress(self, chunk_summaries, document_id, output_file="progress_summaries.json"):
        """Sauvegarde la progression des résumés dans un fichier JSON."""
        # Structure des données avec l'ID du fichier comme clé
        print("saving")

        progress_data = {
            document_id: {  # Clé = ID du fichier
                "chunk_summaries": [chunk_summary for chunk_summary in chunk_summaries],
                "last_updated_chunk": len(chunk_summaries),
                "timestamp": datetime.datetime.now().isoformat(),
                "model": self.model,
                "window_size": self.window_size,
                "max_summary_len": self.max_summary_len,
                "word_per_token_ratio": self.word_per_token_ratio,
            }
        }

        # Charge les données existantes si le fichier existe déjà
        existing_data = {}
        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)

        # Met à jour les données existantes avec les nouvelles données
        existing_data.update(progress_data)

        # Écrit dans le fichier
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)

        print(f"Progression sauvegardée dans {output_file}.")