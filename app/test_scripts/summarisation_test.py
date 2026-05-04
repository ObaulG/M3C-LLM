import os
from summariser import Summariser
from helper import extract_text_from_pdf

DOCUMENT_ID = "dbd5f14a9e6545880b0cd505583ea7d1fe1e8b3d.pdf"
FOLDER = r"C:\Users\xenyi\Documents\Ressources-Pro\Thèse\M3C-documents"
# --- Schémas et agents (inchangés) ---
# (Utilisez les définitions de SummarizeRequestInput, SummaryResult, RecommendationRequestInput, RecommendationResult, et les agents get_summary_agent et get_recommendation_agent de la réponse précédente)


def main():
    summariser = Summariser("mistral-large-latest")
    summary = summariser.summarise(DOCUMENT_ID, os.path.join(FOLDER, DOCUMENT_ID))
    print(summary)

if __name__ == "__main__":
    main()
