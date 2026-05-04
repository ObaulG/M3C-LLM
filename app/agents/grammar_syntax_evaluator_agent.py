from atomic_agents.context import SystemPromptGenerator

from answer_evaluator_agent import EvaluateRequestInput, AgentEvaluationResult

evaluation_system_prompt_generator = SystemPromptGenerator(
    background=[
        "Cet agent évalue la grammaire et la syntaxe d'un texte.",
        "Il attribue une note de 1 à 10.",
    ],
    steps=[
        "Vérifier l'orthographe et la syntaxe du texte",
        "Attribuer une note de 1 à 10 (1 = complètement incorrect, 10 = complet).",
        "Fournir un commentaire pour expliquer la note.",
    ],
    output_instructions=[
        "La note doit être un entier entre 1 et 10.",
        "Le commentaire doit être clair, constructif et en français.",
        "L'évaluation doit être légère. Ne pas pénaliser si l'utilisateur donne une réponse cohérente."
    ],
)