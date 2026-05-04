import os
import pickle
from pathlib import Path
from pdf_extractor import extract_text_from_pdf
from langchain_mistralai import MistralAIEmbeddings, ChatMistralAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

if __name__ == '__main__':
    llm = ChatMistralAI(
        model="mistral-medium-latest",
        temperature=0.7,
        max_retries=2,
        mistral_api_key=os.getenv("MISTRAL_API_KEY"),
        # other params...
    )

    initial_prompt = """
        Tu es un chercheur en informatique appliquée au domaine culturel. Voici une liste de critères à étudier dans les articles qui te seront fournis : 
        Type de modèle; Open-source / propriétaire; Implémentation (API / local / cloud); Coût et financement; Méthode d'adaptation (fine-tuning, RAG, etc.); Combinaison ou multi-agent; Corpus d’entraînement; Sources patrimoniales utilisées; Transparence des données; Type d'application; Type de public visé; Méthode d’évaluation utilisateur; Changement de pratiques observé; Interopérabilité (BDD, ontologies, formats); Critères éthiques (écoconception, biais, PI); Reproductibilité (code, données, protocole); Niveau de maturité (TRL); Impact culturel / sociétal; Remarques / synthèse
        Lorsqu'un article te sera donné, tu rempliras chaque critère en un ou 2 mots. Si tu ne sais pas, laisse le critère vide
    """

    messages = [
        (
            "system",
            initial_prompt
        )
    ]

    folder = Path("docs")
    docs_studied = []
    with open("docs-studied.txt", "r") as f:
        docs_studied.extend(f.read().splitlines())

    result_file = "result.txt"

    for fichier in folder.glob("*.pdf"):
        print(f"Traitement du fichier : {fichier.name}")
        pdf_text = extract_text_from_pdf(fichier)
        print(f"Longueur du texte extrait : {len(pdf_text)} caractères\n")

        # ajouter à la fin
        with open(result_file, "a") as f:
            pass
