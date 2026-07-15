# agents/qa_agent.py
from atomic_agents import AtomicAgent, AgentConfig, BaseIOSchema
from atomic_agents.context import SystemPromptGenerator, ChatHistory

from .instructor_factory import create_client
from .prompt_loader import get_prompt
from instructor import Mode


class QuestionRequestInput(BaseIOSchema):
    """
    This schema represent the input of a user or a agent requesting questions/answers
     from a given document.
    The message can give instructions on how to generate questions/answers
    """
    message: str
    document: str
    num_questions: int

class QuestionAnswer(BaseIOSchema):
    """
    The result of a question/answer generation.
    """
    question: str
    answer: str

class QuestionAnswerList(BaseIOSchema):
    """
    A list of questions/answers
    """
    QA_list: list[QuestionAnswer]

system_prompt_generator = get_prompt("qa_single", "default")

def get_qa_agent(model: str = "mistral-small", provider: str = "mistral", async_mode: bool = False):
    client = create_client(provider, model, async_mode=async_mode, instructor_mode=Mode.JSON)
    agent = AtomicAgent[QuestionRequestInput, QuestionAnswerList](
        config=AgentConfig(
            client=client,
            model=model,
            history=None,
            tools=None,
            system_prompt_generator=system_prompt_generator,
        )
    )
    return agent
