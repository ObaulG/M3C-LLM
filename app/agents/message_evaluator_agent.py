from typing import Literal, List
from atomic_agents import BaseIOSchema, AtomicAgent, AgentConfig
from atomic_agents.context import SystemPromptGenerator, ChatHistory
from .mistral_client import get_mistral_client
from .prompt_loader import get_prompt

class MessageTypeRequestInput(BaseIOSchema):
    """
    Schema pour l'entree de l'agent de classification de message.
    Contient la question initiale, les reponses de reference, et la reponse de l'utilisateur.
    """
    current_question: str
    reference_answers: List[str]
    user_message: str

class MessageTypeResult(BaseIOSchema):
    """
    Resultat de la classification du message utilisateur.
    """
    message_type: Literal["reponse", "demande_renseignement", "hors_sujet", "autre"]
    confidence: float
    explanation: str


# Fallback definition
_FALLBACK_PROMPT = SystemPromptGenerator(
    background=[
        "Cet agent est specialise dans la classification des messages utilisateurs en fonction de leur pertinence par rapport a une question initiale.",
        "Il doit determinant si le message est une reponse a la question ou hors sujet.",
        "La classification doit etre precise et justifiee.",
        "L'agent recoit la question, LES REPONSES DE REFERENCE attendues, et le message de l'utilisateur.",
        "reponse: repond a la question en cours, ou contient suffisamment d'elements presents dans les reponses de reference",
        "hors-sujet: demande qui ne concerne pas de pres ou de loin la question ou ses reponses attendues",
        "autre: tous les autres cas de figure"
    ],
    steps=[
        "Lire la question initiale, LES REPONSES DE REFERENCE, et le message de l'utilisateur.",
        "Determiner si le message est dans le même contexte que la question ou les reponses de reference. ",
        "Comparer le message de l'utilisateur avec LES REPONSES DE REFERENCE pour detecter des elements communs.",
        "Attribuer un niveau de confiance a la classification (0.0 = incertain, 1.0 = certain).",
        "Fournir une explication claire et concise de la classification.",
    ],
    output_instructions=[
        "Le champ message_type doit etre l'une des valeurs suivantes : 'reponse', 'hors_sujet'.",
        "Une seule valeur a retourner.",
        "Ne classe pas hors_sujet des messages qui contiennent des elements communs avec les reponses de reference",
        "Exemple: si la question parle de transport ferroviaire et que les reponses de reference mentionnent train et TGV, et que la réponse utilisateur contient train, alors il est très probable que la réponse soit bien dans le contexte"
        "Le champ confidence doit etre un float entre 0.0 et 1.0.",
        "Le champ explanation doit expliquer brièvement la raison de la classification, en mentionnant quels elements du message correspondent aux reponses de reference.",
        "La reponse doit etre redigee en francais et adaptee au contexte.",
    ],
)

# Charger depuis YAML
message_type_system_prompt_generator = get_prompt("message_evaluator", "message_type")
if message_type_system_prompt_generator is None:
    message_type_system_prompt_generator = _FALLBACK_PROMPT


def get_message_type_agent(model: str = "ministral-3b-2410"):
    client = get_mistral_client()
    message_type_agent = AtomicAgent[MessageTypeRequestInput, MessageTypeResult](
        config=AgentConfig(
            client=client,
            model=model,
            history=None,
            system_prompt_generator=message_type_system_prompt_generator,
        )
    )
    return message_type_agent
