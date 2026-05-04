import json
import re
from typing import Optional, List

from atomic_agents import BaseIOSchema, AtomicAgent, AgentConfig
from atomic_agents.context import SystemPromptGenerator, ChatHistory
from instructor import Mode

from .instructor_factory import create_client

class EvaluateRequestInput(BaseIOSchema):
    """
    Schema pour l'entrée de l'agent d'évaluation.
    Contient la question, la réponse attendue et la réponse de l'utilisateur.
    """
    question: str
    expected_answer: str
    user_answer: str

class AgentEvaluationResult(BaseIOSchema):
    """
    Contains the evaluation given by a LM to the answer.
    """
    score: int  # Note de 1 à 10
    feedback: str  # Commentaire sur la réponse

class ListAgentEvaluationResult(BaseIOSchema):
    """
    A list of evaluation results, meant to be summarized.
    """
    evaluations: List[AgentEvaluationResult]


evaluation_system_prompt_generator = SystemPromptGenerator(
    background=[
        "Tu es un agent d’évaluation spécialisé dans l’analyse de réponses à des questions de compréhension.",
        "Tu compares la réponse de l’utilisateur avec la réponse attendue."
    ],
    steps=[
        "Analyser précisément la question.",
        "Identifier les éléments essentiels dans la réponse attendue.",
        "Comparer avec la réponse de l’utilisateur.",
        "Évaluer la pertinence et l’exactitude.",
        "Déterminer une note entière entre 1 et 10."
    ],
    output_instructions=[
        "Tu dois répondre UNIQUEMENT avec un objet JSON valide.",
        "Ne produis aucun texte avant ou après le JSON.",
        "Le JSON doit avoir EXACTEMENT cette structure :",
        '{ "score": <entier entre 1 et 10>, "feedback": "<texte en français>" }',
        "Le champ score doit être un entier compris entre 1 et 10.",
        "Le champ feedback doit être un texte rédigé, clair, constructif et en français.",
        "Ne jamais mentionner le mot 'score' ou la note chiffrée dans le feedback.",
        "Ne pas ajouter d’autres champs.",
        "Ne pas reformuler la question.",
        "Ne pas expliquer ton raisonnement."
    ],
)

evaluation_system_prompt_generator_bis = SystemPromptGenerator(
    background=[
        "Tu es un agent d’évaluation spécialisé dans l’analyse de réponses à des questions de compréhension.",
        "Tu compares la réponse de l’utilisateur avec la réponse attendue."
    ],
    steps=[
        "Analyser précisément la question.",
        "Identifier les éléments essentiels dans la réponse attendue.",
        "Comparer avec la réponse de l’utilisateur.",
        "Évaluer la pertinence et l’exactitude.",
        "Déterminer une note entière entre 1 et 10."
    ],
    output_instructions=[
        "Tu dois répondre UNIQUEMENT avec un objet JSON valide dans un bloc ```json.",
        "Ne produis aucun texte avant ou après le JSON.",
        "Le JSON doit avoir EXACTEMENT cette structure :",
        '{ "score": <entier entre 1 et 10>, "feedback": "<texte en français>" }',
        "Le champ score doit être un entier compris entre 1 et 10.",
        "Le champ feedback doit être un texte rédigé, clair, constructif et en français.",
        "Ne jamais mentionner le mot 'score' ou la note chiffrée dans le feedback.",
        "Ne pas ajouter d’autres champs.",
        "Ne pas reformuler la question.",
        "Ne pas expliquer ton raisonnement."
    ],
)

final_evaluation_system_prompt_generator = SystemPromptGenerator(
    background=[
        "Cet agent est spécialisé dans la synthèse des évaluations fournies par plusieurs évaluateurs.",
        "Il reçoit les notes et commentaires de plusieurs évaluateurs et doit proposer une seule évaluation finale, avec une note sur 10.",
        "Il doit fournir un message final, écrit sur un ton naturel, qui sera affiché à l'utilisateur.",
    ],
    steps=[
        "Analyser les notes et commentaires de chaque évaluateur.",
        "Identifier les points communs et les divergences entre les évaluations.",
        "Calculer une note finale qui reflète le consensus des évaluateurs.",
        "Prendre en compte la cohérence globale des réponses et l'équité des évaluations.",
        "Rédiger un commentaire final qui synthétise les retours des évaluateurs.",
        "Rédiger le message qui sera donné à l'utilisateur"
    ],
    output_instructions=[
        "La note finale doit être un entier entre 1 et 10. Avec moins de 7, l'utilisateur doit recommencer.",
        "Le commentaire final doit être clair, concis, constructif et en français.",
        "Le message final doit rebondir sur la réponse de l'utilisateur. S'il a oublié des détails, alors ce sera précisé dans le message.",
        "Ne pas mentionner la note dans la réponse rédigée.",
        "Si l'utilisateur doit recommencer, alors on pourra lui suggérer, indirectement, ce qu'ils devrait rajouter."
    ],
)

def get_final_evaluator_agent(model: str = "mistral-medium",
                              provider: str = "mistral",
                              async_mode: bool = False):
    client = create_client(provider, async_mode)
    final_evaluation_agent = AtomicAgent[ListAgentEvaluationResult, AgentEvaluationResult](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=final_evaluation_system_prompt_generator,
        )
    )
    return final_evaluation_agent

def get_evaluator_agent(model: str = "mistral-medium",
                              provider: str = "mistral",
                              async_mode: bool = False,
                              custom_system_prompt_generator=None):
    system_prompt_generator = custom_system_prompt_generator if custom_system_prompt_generator else evaluation_system_prompt_generator
    client = create_client(provider, model=None, async_mode=async_mode)
    # Supprimer format json en cas d'erreur
    evaluation_agent = AtomicAgent[EvaluateRequestInput, AgentEvaluationResult](
        config=AgentConfig(
            client=client,
            model=model,
            mode=Mode.JSON,
            history=ChatHistory(),
            tools=[],
            system_prompt_generator=system_prompt_generator,
            model_api_parameters={"temperature": 0.05,},
        )
    )
    return evaluation_agent

def get_evaluator_agent_local(model: str = "ministral-3:3b",
                              provider: str = "ollama",
                              async_mode: bool = False):
    client = create_client(provider, async_mode)
    evaluation_agent = AtomicAgent[EvaluateRequestInput, str](
        config=AgentConfig(
            client=client,
            model=model,
            mode=Mode.MD_JSON,
            history=ChatHistory(),
            tools=None,
            system_prompt_generator=evaluation_system_prompt_generator_bis,
            model_api_parameters={"temperature": 0.05},
        )
    )
    return evaluation_agent

async def run_raw(agent, input_data: EvaluateRequestInput) -> AgentEvaluationResult:
    """
    Effectué
    """
    raw_output = await agent.run_async(input_data)

    # 1️⃣ Extraire bloc JSON si présent
    match = re.search(r"```json\s*(.*?)\s*```", raw_output, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        json_str = raw_output.strip()

    # 2️⃣ Charger JSON
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON returned by model:\n{raw_output}") from e

    # 3️⃣ Validation Pydantic
    return AgentEvaluationResult.model_validate(data)