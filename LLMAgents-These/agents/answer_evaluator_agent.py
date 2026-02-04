from typing import Optional

from atomic_agents import BaseIOSchema, AtomicAgent, AgentConfig
from atomic_agents.context import SystemPromptGenerator, ChatHistory
from .mistral_client import get_mistral_client

class EvaluateRequestInput(BaseIOSchema):
    """
    Schema pour l'entrée de l'agent d'évaluation.
    Contient la question, la réponse attendue et la réponse de l'utilisateur.
    """
    question: str
    expected_answer: str
    user_answer: str

class EvaluationResult(BaseIOSchema):
    """
    Contains the evaluation given by a LM to the answer. Also, with cos sim.
    """
    score: int  # Note de 1 à 10
    feedback: str  # Commentaire sur la réponse
    cosine_similarity: Optional[float]  # Similarité cosinus entre la question et la réponse

evaluation_system_prompt_generator = SystemPromptGenerator(
    background=[
        "Cet agent est spécialisé dans l'évaluation des réponses des utilisateurs à des questions de compréhension.",
        "Il compare la réponse de l'utilisateur avec la réponse attendue et attribue une note de 1 à 10.",
    ],
    steps=[
        "Analyser la question et la réponse attendue.",
        "Comparer la réponse de l'utilisateur avec la réponse attendue.",
        "Évaluer la pertinence de la réponse.",
        "Attribuer une note de 1 à 10 (1 = complètement incorrect, 10 = complet).",
        "Fournir un commentaire constructif pour expliquer la note.",
    ],
    output_instructions=[
        "La note doit être un entier entre 1 et 10.",
        "Le commentaire doit être clair, constructif et en français.",
        "L'évaluation doit être légère. Ne pas pénaliser si l'utilisateur donne une réponse cohérente."
        "Ne pas pénaliser si l'utilisateur rajoute du contexte si cela est pertinent.",
        "La réponse doit être rédigée. Pas de réponse en mots-clefs."
    ],
)

def get_evaluator_agent(model: str = "mistral-medium"):
    client = get_mistral_client()
    evaluation_agent = AtomicAgent[EvaluateRequestInput, EvaluationResult](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=evaluation_system_prompt_generator,
        )
    )
    return evaluation_agent