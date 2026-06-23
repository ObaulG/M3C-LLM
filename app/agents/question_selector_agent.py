# agents/question_selector.py
from atomic_agents import AtomicAgent, AgentConfig, BaseIOSchema
from atomic_agents.context import SystemPromptGenerator, ChatHistory
from typing import List, Optional

from .qa_agent import get_qa_agent

from .mistral_client import get_mistral_client

from pydantic import BaseModel
from typing import List, Optional

from database.database import get_questions_by_document_id

class QuestionSelectionInput(BaseModel):
    """
    Entree pour la selection de questions.
    """
    document_id: str
    document_content: str
    num_questions: int = 3
    existing_questions: Optional[List[dict]] = None

class SelectedQuestion(BaseModel):
    """
    Une question selectionnee ou generee.
    """
    question_text: str
    answer_text: str
    source: str

class SelectedQuestionsList(BaseModel):
    """
    Liste des questions selectionnees.
    """
    questions: List[SelectedQuestion]


# Fallback definition
_FALLBACK_PROMPT = SystemPromptGenerator(
    background=[
        "Cet agent selectionne ou genere des questions/reponses a partir d'un document ou d'une base de donnees.",
        "Il privilegiera les questions existantes (humaines ou validees) avant de generer de nouvelles questions.",
    ],
    steps=[
        "Verifier si des questions existantes sont fournies ou disponibles en base de donnees.",
        "Si des questions existent, les selectionner en priorite.",
        "Si le nombre de questions est insuffisant, generer les questions manquantes avec l'agent QA.",
        "Retourner une liste de questions selectionnees ou generees.",
    ],
    output_instructions=[
        "Retourner exactement le nombre de questions demande.",
        "Privilégier les questions existantes (source: 'database' ou 'human').",
        "Pour les questions generees, indiquer la source: 'generated'.",
    ],
)


class QuestionSelectorAgent(AtomicAgent[QuestionSelectionInput, SelectedQuestionsList]):
    def __init__(self, model: str = "mistral-medium"):
        from .prompt_loader import get_prompt
        
        # Initialiser l'agent QA pour generer des questions si necessaire
        self.qa_agent = get_qa_agent(model, "mistral", False)

        # Prompt systeme pour l'agent de selection
        loaded = get_prompt("question_selector", "default")
        system_prompt_generator = loaded if loaded is not None else _FALLBACK_PROMPT

        super().__init__(
            config=AgentConfig(
                client=get_mistral_client(),
                model=model,
                history=ChatHistory(),
                system_prompt_generator=system_prompt_generator,
            )
        )

    def run(self, input_data: QuestionSelectionInput) -> SelectedQuestionsList:
        """
        Selectionne ou genere des questions en fonction des entrees.
        """
        selected_questions = []

        # 1. Recuperer les questions existantes (depuis la base de donnees ou l'entree)
        existing_questions = input_data.existing_questions or []
        if not existing_questions:
            existing_questions = get_questions_by_document_id(input_data.document_id)

        # 2. Ajouter les questions existantes a la liste
        for q in existing_questions:
            selected_questions.append(
                SelectedQuestion(
                    question_text=q["question_text"],
                    answer_text=q["answer_text"],
                    source=q.get("source", "database")
                )
            )

        # 3. Generer les questions manquantes si necessaire
        if len(selected_questions) < input_data.num_questions:
            num_missing = input_data.num_questions - len(selected_questions)
            generated_questions = self._generate_questions(
                input_data.document_content,
                num_missing
            )
            selected_questions.extend(generated_questions)

        return SelectedQuestionsList(questions=selected_questions)

    def _generate_questions(self, document_content: str, num_questions: int) -> List[SelectedQuestion]:
        """
        Genere de nouvelles questions avec l'agent QA.
        """
        response = self.qa_agent.run({
            "message": f"Genere {num_questions} questions.",
            "document": document_content
        })

        return [
            SelectedQuestion(
                question_text=qa.question_text,
                answer_text=qa.answer_text,
                source="generated"
            )
            for qa in response.questions_answers
        ]


