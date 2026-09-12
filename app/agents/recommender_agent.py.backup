from typing import List, Dict
from atomic_agents import BaseIOSchema, AtomicAgent, AgentConfig
from atomic_agents.context import SystemPromptGenerator, ChatHistory
from .mistral_client import get_mistral_client

class RecommendationRequestInput(BaseIOSchema):
    """
    Schema pour l'entrée de l'agent de recommandation.
    Contient les préférences de l'utilisateur et les résumés des documents.
    """
    user_preferences: str  # Préférences de l'utilisateur (ex: "histoire, nature, traditions")
    document_summaries: List[Dict[str, str]]  # Liste de dictionnaires: {"title": str, "summary": str, "keywords": List[str]}

class RecommendationResult(BaseIOSchema):
    """
    Contient le document recommandé et la justification.
    """
    recommended_document: str  # Titre du document recommandé
    justification: str  # Justification de la recommandation

# Générateur de prompt système pour l'agent recommandeur
recommendation_system_prompt_generator = SystemPromptGenerator(
    background=[
        "Cet agent recommande un document en fonction des préférences de l'utilisateur (ex: histoire, nature, traditions) et des résumés/mots-clés des documents disponibles sur la Corse.",
        "Il doit analyser les préférences et les comparer avec les résumés et mots-clés pour trouver le meilleur match.",
        "Les documents peuvent être des livres, des articles ou des rapports de plusieurs centaines de pages.",
    ],
    steps=[
        "1. Lire attentivement les préférences de l'utilisateur.",
        "2. Analyser les résumés et les mots-clés de chaque document.",
        "3. Identifier le document dont le contenu (résumé + mots-clés) correspond le mieux aux préférences de l'utilisateur.",
        "4. Justifier la recommandation en expliquant les points de correspondance entre les préférences et le contenu du document.",
    ],
    output_instructions=[
        "La recommandation doit être claire et justifiée.",
        "Privilégier les documents dont les mots-clés ou le résumé contiennent explicitement les thèmes mentionnés par l'utilisateur.",
        "Si aucun document ne correspond parfaitement, recommander celui qui couvre le plus de thèmes parmi les préférences.",
        "La justification doit être rédigée en français, de manière concise et informative.",
    ],
)

def get_recommendation_agent(model: str = "mistral-medium"):
    """
    Crée et retourne un agent spécialisé dans la recommandation de documents.
    """
    client = get_mistral_client()
    recommendation_agent = AtomicAgent[RecommendationRequestInput, RecommendationResult](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=recommendation_system_prompt_generator,
        )
    )
    return recommendation_agent
