from atomic_agents import AtomicAgent, AgentConfig, BaseIOSchema
from atomic_agents.context import SystemPromptGenerator, ChatHistory

from .mistral_client import get_mistral_client
from .prompt_loader import get_prompt

class FactExtractionInput(BaseIOSchema):
    """
    This schema represents the input for the fact extraction agent.
    It takes a paragraph from a document to extract facts.
    """
    paragraph: str

class FactExtractionOutput(BaseIOSchema):
    """
    The result of the fact extraction.
    A list of facts extracted from the paragraph.
    """
    facts: list[str]


# Fallback definition
_FALLBACK_PROMPT = SystemPromptGenerator(
    background=[
        "This agent is specialized in extracting key facts from a given paragraph.",
    ],
    steps=[
        "Analyze the paragraph to identify key facts",
        "Extract the relevant information as concise facts",
        "Organize the facts in a clear and logical order",
    ],
    output_instructions=[
        "List each fact as a separate item",
        "Be concise and clear",
        "Use short sentences",
        "Do not add any commentary or interpretation",
        "Write in French",
    ],
)

# Charger depuis YAML
system_prompt_generator = get_prompt("fact_extractor", "default")
if system_prompt_generator is None:
    system_prompt_generator = _FALLBACK_PROMPT


def get_fact_analyser_agent(model: str = "mistral-medium"):
    client = get_mistral_client()
    agent = AtomicAgent[FactExtractionInput, FactExtractionOutput](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=system_prompt_generator,
        )
    )
    return agent


class FactPresenceInput(BaseIOSchema):
    """This schema represents the input for the fact presence agent.
    It takes a user answer and the list of facts to check against it."""
    user_answer: str
    facts: list[str]


class FactJudgement(BaseIOSchema):
    """Verdict for a single fact."""
    fact_index: int
    verdict: str
    justification: str


class FactPresenceOutput(BaseIOSchema):
    """The result of the fact presence check: one judgement per fact, in order."""
    judgements: list[FactJudgement]


_FALLBACK_PRESENCE_PROMPT = SystemPromptGenerator(
    background=[
        "Tu es un agent d'évaluation qui vérifie si des affirmations factuelles sont présentes dans la réponse d'un utilisateur.",
    ],
    steps=[
        "Analyse la réponse de l'utilisateur dans son ensemble.",
        "Pour chaque affirmation de la liste, détermine si l'information qu'elle porte est présente dans la réponse.",
        "Accepte les reformulations et les synonymes : la présence ne nécessite pas les mots exacts, sauf pour les noms propres.",
        "Attribue à chaque affirmation un verdict: \"present\", \"partial\" ou \"absent\".",
        "Rédige pour chaque affirmation une justification brève en français.",
    ],
    output_instructions=[
        "Retourne uniquement un JSON avec une liste \"judgements\", une entrée par affirmation, dans l'ordre.",
        "Chaque entrée: {\"fact_index\": <index 0-based>, \"verdict\": \"present\"|\"partial\"|\"absent\", \"justification\": \"<texte bref>\"}",
        "Ne saute aucune affirmation, n'en ajoute pas, ne modifie pas leur ordre.",
        "Écris en français.",
    ],
)

_fact_presence_prompt = get_prompt("fact_extractor", "fact_presence")
if _fact_presence_prompt is None:
    _fact_presence_prompt = _FALLBACK_PRESENCE_PROMPT


def get_fact_presence_agent(model: str = "mistral-medium"):
    client = get_mistral_client()
    agent = AtomicAgent[FactPresenceInput, FactPresenceOutput](
        config=AgentConfig(
            client=client,
            model=model,
            history=None,
            system_prompt_generator=_fact_presence_prompt,
        )
    )
    return agent
