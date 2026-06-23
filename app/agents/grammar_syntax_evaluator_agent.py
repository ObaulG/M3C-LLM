from atomic_agents.context import SystemPromptGenerator
from .answer_evaluator_agent import EvaluateRequestInput, AgentEvaluationResult
from .prompt_loader import get_prompt


# Fallback definition
_FALLBACK_PROMPT = SystemPromptGenerator(
    background=[
        "Cet agent evalue la grammaire et la syntaxe d'un texte.",
        "Il attribue une note de 1 a 10.",
    ],
    steps=[
        "Verifier l'orthographe et la syntaxe du texte",
        "Attribuer une note de 1 a 10 (1 = completement incorrect, 10 = complet).",
        "Fournir un commentaire pour expliquer la note.",
    ],
    output_instructions=[
        "La note doit etre un entier entre 1 et 10.",
        "Le commentaire doit etre clair, constructif et en francais.",
        "L'evaluation doit etre legere. Ne pas penaliser si l'utilisateur donne une reponse coherente."
    ],
)

# Charger depuis YAML (utilise le prompt de evaluators.yaml)
evaluation_system_prompt_generator = get_prompt("evaluators", "grammar_syntax_evaluation")
if evaluation_system_prompt_generator is None:
    evaluation_system_prompt_generator = _FALLBACK_PROMPT
