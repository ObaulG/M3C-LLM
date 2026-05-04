from typing import Literal
from atomic_agents import BaseIOSchema, AtomicAgent, AgentConfig
from atomic_agents.context import SystemPromptGenerator, ChatHistory
from .mistral_client import get_mistral_client

class MessageTypeRequestInput(BaseIOSchema):
    """
    Schema pour l'entrée de l'agent de classification de message.
    Contient la question initiale et la réponse de l'utilisateur.
    """
    current_question: str
    user_message: str

class MessageTypeResult(BaseIOSchema):
    """
    Résultat de la classification du message utilisateur.
    """
    message_type: Literal["réponse", "demande_renseignement", "hors_sujet", "autre"]  # Type de message
    confidence: float  # Niveau de confiance (0.0 à 1.0)
    explanation: str  # Explication de la classification

message_type_system_prompt_generator = SystemPromptGenerator(
    background=[
        "Cet agent est spécialisé dans la classification des messages utilisateurs en fonction de leur pertinence par rapport à une question initiale.",
        "Il doit déterminer si le message est une réponse à la question, une demande de renseignements supplémentaires, ou hors sujet.",
        "La classification doit être précise et justifiée.",
        "réponse: répond à la question en cours",
        "renseignement: demande une information en lien direct ou indirect avec la question, mais il ne répond pas",
        "hors-sujet: demande qui ne concerne pas de près ou de loin la question",
        "autre: tous les autres cas de figure"
    ],
    steps=[
        "Lire attentivement la question initiale et le message de l'utilisateur.",
        "Déterminer si le message est une réponse directe à la question (réponse).",
        "Déterminer si le message est une demande de précisions ou d'informations complémentaires (demande_renseignement).",
        "Déterminer si le message n'a aucun lien avec la question (hors_sujet).",
        "Attribuer un niveau de confiance à la classification (0.0 = incertain, 1.0 = certain).",
        "Fournir une explication claire et concise de la classification.",
    ],
    output_instructions=[
        "Le champ `message_type` doit être l'une des valeurs suivantes : 'réponse', 'demande_renseignement', 'hors_sujet'.",
        "Une seule valeur à retourner.",
        "Le champ `confidence` doit être un float entre 0.0 et 1.0.",
        "Le champ `explanation` doit expliquer brièvement la raison de la classification.",
        "La réponse doit être rédigée en français et adaptée au contexte.",
    ],
)

def get_message_type_agent(model: str = "mistral-small"):
    client = get_mistral_client()
    message_type_agent = AtomicAgent[MessageTypeRequestInput, MessageTypeResult](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=message_type_system_prompt_generator,
        )
    )
    return message_type_agent
