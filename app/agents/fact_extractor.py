from atomic_agents import AtomicAgent, AgentConfig, BaseIOSchema
from atomic_agents.context import SystemPromptGenerator, ChatHistory

from .mistral_client import get_mistral_client
from .prompt_loader import get_prompt

class AnswerFact(BaseIOSchema):
    """
    A single fact from a reference answer, with its importance.
    importance: "essential" (indispensable à la réponse) ou "optional"
    (information secondaire qui consolide un fait principal, ou fait
    d'une énumération au même niveau d'importance).
    """
    content: str
    importance: str


class AnswerFactsExtractionOutput(BaseIOSchema):
    """
    The result of the answer decomposition into facts with importance.
    """
    facts: list[AnswerFact]


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


def get_fact_presence_agent(model: str = "mistral-medium",
                            provider: str = "mistral",
                            async_mode: bool = False):
    from .instructor_factory import create_client
    import instructor

    if provider == "ollama":
        instructor_mode = instructor.Mode.JSON
        client = create_client(provider, model, async_mode, instructor_mode=instructor_mode)
        model_api_parameters = {"temperature": 0.35, "max_tokens": 8192 if "qwen" in model else 2048, "reasoning_effort": "none"}
    else:
        instructor_mode = instructor.Mode.JSON
        client = create_client(provider, model, async_mode, instructor_mode=instructor_mode)
        model_api_parameters = {"temperature": 0.35} if provider not in ["gemini", "google"] else {}
    agent = AtomicAgent[FactPresenceInput, FactPresenceOutput](
        config=AgentConfig(
            client=client,
            model=model,
            mode=instructor_mode,
            history=None,
            system_prompt_generator=_fact_presence_prompt,
            model_api_parameters=model_api_parameters,
            assistant_role="model" if provider in ["gemini", "google"] else "assistant",
        )
    )
    return agent


_FALLBACK_ANSWER_FACTS_PROMPT = SystemPromptGenerator(
    background=[
        "Tu es un agent spécialisé dans la décomposition d'une réponse de référence en affirmations atomiques, avec leur niveau d'importance.",
    ],
    steps=[
        "Analyse la réponse et identifie toutes les affirmations factuelles qu'elle contient.",
        "Pour chaque affirmation, détermine son importance : \"essential\" si l'information est indispensable pour que la réponse soit correcte ou complète, \"optional\" s'il s'agit d'une information secondaire qui apporte de la consistance à un fait principal, ou d'un fait d'une énumération au même niveau d'importance que les autres.",
        "Rédige chaque affirmation sous forme de phrase courte, claire et autonome.",
    ],
    output_instructions=[
        "Retourne uniquement un JSON avec une liste \"facts\".",
        "Chaque entrée: {\"content\": \"<affirmation>\", \"importance\": \"essential\"|\"optional\"}",
        "Une réponse peut contenir plusieurs faits essentiels (ex: une énumération où tous les éléments ont le même niveau d'importance).",
        "Ne pas ajouter de commentaire ni d'interprétation.",
        "Écris en français.",
    ],
)

_answer_facts_prompt = get_prompt("fact_extractor", "answer_facts")
if _answer_facts_prompt is None:
    _answer_facts_prompt = _FALLBACK_ANSWER_FACTS_PROMPT


def get_answer_facts_agent(model: str = "mistral-medium"):
    client = get_mistral_client()
    agent = AtomicAgent[FactExtractionInput, AnswerFactsExtractionOutput](
        config=AgentConfig(
            client=client,
            model=model,
            history=None,
            system_prompt_generator=_answer_facts_prompt,
        )
    )
    return agent
