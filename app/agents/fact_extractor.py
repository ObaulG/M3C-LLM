from atomic_agents import AtomicAgent, AgentConfig, BaseIOSchema
from atomic_agents.context import SystemPromptGenerator, ChatHistory

from .mistral_client import get_mistral_client

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

system_prompt_generator = SystemPromptGenerator(
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