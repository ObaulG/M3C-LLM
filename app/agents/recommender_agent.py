from typing import List, Dict
from atomic_agents import BaseIOSchema, AtomicAgent, AgentConfig
from atomic_agents.context import SystemPromptGenerator, ChatHistory
from .mistral_client import get_mistral_client
from .prompt_loader import get_prompt

class RecommendationRequestInput(BaseIOSchema):
    """
    Schema pour l'entree de l'agent de recommandation.
    Contient les preferences de l'utilisateur et les resumes des documents.
    """
    user_preferences: str
    document_summaries: List[Dict[str, str]]

class RecommendationResult(BaseIOSchema):
    """
    Contient le document recommande et la justification.
    """
    recommended_document: str
    justification: str


# Fallback definition
_FALLBACK_PROMPT = SystemPromptGenerator(
    background=[
        "Cet agent recommande un document en fonction des preferences de l'utilisateur (ex: histoire, nature, traditions) et des resumes/mots-cles des documents disponibles sur la Corse.",
        "Il doit analyser les preferences et les comparer avec les resumes et mots-cles pour trouver le meilleur match.",
        "Les documents peuvent etre des livres, des articles ou des rapports de plusieurs centaines de pages.",
    ],
    steps=[
        "1. Lire attentivement les preferences de l'utilisateur.",
        "2. Analyser les resumes et les mots-cles de chaque document.",
        "3. Identifier le document dont le contenu (resume + mots-cles) correspond le mieux aux preferences de l'utilisateur.",
        "4. Justifier la recommandation en expliquant les points de correspondance entre les preferences et le contenu du document.",
    ],
    output_instructions=[
        "La recommandation doit etre claire et justifiee.",
        "Privilégier les documents dont les mots-cles ou le resume contiennent explicitement les themes mentionnes par l'utilisateur.",
        "Si aucun document ne correspond parfaitement, recommander celui qui couvre le plus de themes parmi les preferences.",
        "La justification doit etre redigee en francais, de maniere concise et informative.",
    ],
)

# Charger depuis YAML
recommendation_system_prompt_generator = get_prompt("recommender", "default")
if recommendation_system_prompt_generator is None:
    recommendation_system_prompt_generator = _FALLBACK_PROMPT


def get_recommendation_agent(model: str = "mistral-medium"):
    """
    Cree et retourne un agent specialise dans la recommandation de documents.
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
