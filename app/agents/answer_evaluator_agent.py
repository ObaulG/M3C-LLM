import json
import re
from typing import Optional, List

from atomic_agents import BaseIOSchema, AtomicAgent, AgentConfig
from atomic_agents.context import SystemPromptGenerator, ChatHistory
from instructor import Mode
import instructor

from .instructor_factory import create_client

class EvaluateRequestInput(BaseIOSchema):
    """
    Schema pour l'entrée de l'agent d'évaluation.
    Contient la question, les réponses attendues et la réponse de l'utilisateur.
    """
    question: str
    expected_answers: List[str]
    user_answer: str
    model: Optional[str] = None

class AgentEvaluationResult(BaseIOSchema):
    """
    Contient le résultat de l'évalaution de l'agent.
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
        "Tu compares la réponse de l’utilisateur avec LES REPONSES ATTENDUES."
    ],
    steps=[
        "Analyser précisément la question.",
        "Identifier les éléments essentiels dans LES REPONSES ATTENDUES.",
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
        "Les questions sont basés sur des documents culturels liés à la Corse."
        "Tu compares la réponse de l’utilisateur avec LES REPONSES ATTENDUES et tu fais un retour."
        "Question: Pourquoi le col de Teghime est-il considéré comme un lieu symbolique pour les Bastiais ?",
        "Réponse référence : Le col de Teghime est symbolique pour les Bastiais car il leur permet de traverser d'est en ouest et offre une vue sur ce qu'ils appellent « les deux mers », une division imaginaire de la Méditerranée en deux parties, dont la Tyrrhénienne.",
        "Réponse utilisateur 1 : Teghime coupe symboliquement la Méditerranée en deux mers, et crée la Tyrrhénienne.",
        "Note 1 : 7",
        "feedback 1: En effet, Teghime tranche cette mer en deux. La vue y est d'ailleurs magnifique !"
        "Réponse utilisateur 2 : On a la vue des deux côtés",
        "Note 2: 3",
        "feedback 2 : En effet, la vue de ce col est magnifique. Comment cette vue est-elle perçue de manière symbolique ? (On cherche ici un lien avec la mer)"
    ],
    steps=[
        "Analyser précisément la question.",
        "Identifier les éléments essentiels dans LES REPONSES ATTENDUES.",
        "Comparer avec la réponse de l’utilisateur.",
        "Évaluer la pertinence de la réponse, en vérifiant que les éléments correspondent bien à ce qui est écrit dans les réponses de référence."
        "Attention, l'utilisateur a quand même le droit de reformuler les expressions et termes, tiens en compte."
        "Déterminer une note entière entre 1 et 10."
    ],
    output_instructions=[
        "Tu dois répondre UNIQUEMENT avec un objet JSON valide dans un bloc ```json.",
        "Ne produis aucun texte avant ou après le JSON.",
        "Le JSON doit avoir EXACTEMENT cette structure :",
        '{ "score": <entier entre 1 et 10>, "feedback": "<texte en français>" }',
        "N'utilise JAMAIS de \' dans le JSON. Les apostrophes (') n'ont pas besoin d'être échappées."
        "Le champ score doit être un entier compris entre 1 et 10.",
        "Le champ feedback doit être un texte rédigé, clair, constructif et en français.",
        "Ne jamais mentionner le mot 'score' ou la note chiffrée dans le feedback.",
        "Tu dois avoir un ton de médiateur culturel dans le feedback, avec un ton naturel.",
        "Quand tu compares la réponse utilisateur à la réponse référence, tu ne cherches pas l'exactitude des mots, sauf les noms propres."
        "Si la réponse manque d'informations, relève les informations de la réponse utilisateur,",
        "pose des questions sur les informations manquantes, comme présenté dans l'exemple."
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
    client = create_client(provider, model, async_mode, instructor_mode=instructor.Mode.JSON)
    final_evaluation_agent = AtomicAgent[ListAgentEvaluationResult, AgentEvaluationResult](
        config=AgentConfig(
            client=client,
            model=model,
            history=None,
            system_prompt_generator=final_evaluation_system_prompt_generator,
        )
    )
    return final_evaluation_agent

def get_evaluator_agent(model: str = "mistral-medium",
                        provider: str = "mistral",
                        async_mode: bool = False,
                        custom_system_prompt_generator=None):

    if provider == "ollama":
        return get_evaluator_agent_local_bis(model=model, provider=provider, async_mode=async_mode)
    client = create_client(provider, model=model, async_mode=async_mode)
    # Les modèles gemma ne prennent pas la temperature (ou alors pas sous ce nom)
    model_api_parameters = {"temperature": 0.35,}
    evaluation_agent = AtomicAgent[EvaluateRequestInput, AgentEvaluationResult](
        config=AgentConfig(
            client=client,
            model=model,
            mode=Mode.JSON,
            history=None,
            tools=[],
            system_prompt_generator=evaluation_system_prompt_generator_bis,
            model_api_parameters=model_api_parameters,
        )
    )
    return evaluation_agent

def get_evaluator_agent_local(model: str = "ministral-3:3b",
                              provider: str = "ollama",
                              async_mode: bool = False):
    client = create_client(provider, model, async_mode)
    evaluation_agent = AtomicAgent[EvaluateRequestInput, str](
        config=AgentConfig(
            client=client,
            model=model,
            history=None,
            tools=None,
            system_prompt_generator=evaluation_system_prompt_generator_bis,
            model_api_parameters={"temperature": 0.05, "max_tokens": 2048},
        )
    )
    return evaluation_agent

def get_evaluator_agent_local_bis(model: str = "ministral-3:3b", provider: str = "ollama", async_mode: bool = False):
    # https://github.com/567-labs/instructor/issues/1111
    # il faudrait bien mettre mode=instructor.Mode.JSON directement dans le client
    client = create_client(provider, model, async_mode, instructor_mode=instructor.Mode.JSON)
    parameters = {"temperature": 0.35, "max_tokens": 8192 if "qwen" in model else 2048, "reasoning_effort": "none"}
    evaluation_agent = AtomicAgent[EvaluateRequestInput, AgentEvaluationResult](
        config=AgentConfig(
            client=client,
            model=model,
            mode=instructor.Mode.JSON,
            history=None,
            tools=None,
            system_prompt_generator=evaluation_system_prompt_generator_bis,
            model_api_parameters=parameters,
        )
    )
    return evaluation_agent

async def run_raw(agent, input_data: EvaluateRequestInput) -> AgentEvaluationResult:
    print("run_raw")
    raw_output = await agent.run_async(input_data)
    print("raw_output:\n", raw_output)
    match = re.search(r"```json\s*(.*?)\s*```", raw_output, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        json_str = raw_output.strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON returned by model:\n{raw_output}") from e

    return AgentEvaluationResult.model_validate(data)