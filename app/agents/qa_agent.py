# agents/qa_agent.py
from atomic_agents import AtomicAgent, AgentConfig, BaseIOSchema
from atomic_agents.context import SystemPromptGenerator, ChatHistory

from .mistral_client import get_mistral_client

class QuestionRequestInput(BaseIOSchema):
    """
    This schema represent the input of a user or a agent requesting questions/answers
     from a given document.
    The message can give instructions on how to generate questions/answers
    """
    message: str
    document: str

class QuestionAnswer(BaseIOSchema):
    """
    The result of a question/answer generation.
    """
    question_text: str
    answer_text: str

class QuestionAnswerList(BaseIOSchema):
    """
    A list of questions/answers
    """
    questions_answers: list[QuestionAnswer]

system_prompt_generator = SystemPromptGenerator(
    background=[
        "This agent is specialized in generating comprehension questions and answer from a text.",
    ],
    steps=["analyse the user request",
           "Understand the document content",
           "List the main facts of the text",
           "Generate the questions and their answers from the facts"],
    output_instructions=[
        "The number of questions is given by the user. Default is 3",
        "Questions should not be trivial, the visitor should not answer immediately",
        "Questions should be directly justified by the text",
        "If an information is not clearly present, don't invent it and adapt the question",
        "No questions about who wrote a certain book",
        "Questions and answers in French"
    ],
)

def get_qa_agent(model: str = "mistral-medium"):
    client = get_mistral_client()
    agent = AtomicAgent[QuestionRequestInput, QuestionAnswerList](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=system_prompt_generator,
        )
    )
    return agent
