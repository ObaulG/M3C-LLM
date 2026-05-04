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
    Entrée pour la sélection de questions.
    """
    document_id: str
    document_content: str
    num_questions: int = 3
    existing_questions: Optional[List[dict]] = None  # Questions existantes (ex: depuis la base de données)

class SelectedQuestion(BaseModel):
    """
    Une question sélectionnée ou générée.
    """
    question_text: str
    answer_text: str
    source: str  # "database", "generated", ou "human"

class SelectedQuestionsList(BaseModel):
    """
    Liste des questions sélectionnées.
    """
    questions: List[SelectedQuestion]

class QuestionSelectorAgent(AtomicAgent[QuestionSelectionInput, SelectedQuestionsList]):
    def __init__(self, model: str = "mistral-medium"):
        # Initialiser l'agent QA pour générer des questions si nécessaire
        self.qa_agent = get_qa_agent(model)

        # Prompt système pour l'agent de sélection
        system_prompt_generator = SystemPromptGenerator(
            background=[
                "Cet agent sélectionne ou génère des questions/réponses à partir d'un document ou d'une base de données.",
                "Il privilégie les questions existantes (humaines ou validées) avant de générer de nouvelles questions.",
            ],
            steps=[
                "Vérifier si des questions existantes sont fournies ou disponibles en base de données.",
                "Si des questions existent, les sélectionner en priorité.",
                "Si le nombre de questions est insuffisant, générer les questions manquantes avec l'agent QA.",
                "Retourner une liste de questions sélectionnées ou générées.",
            ],
            output_instructions=[
                "Retourner exactement le nombre de questions demandé.",
                "Privilégier les questions existantes (source: 'database' ou 'human').",
                "Pour les questions générées, indiquer la source: 'generated'.",
            ],
        )

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
        Sélectionne ou génère des questions en fonction des entrées.
        """
        selected_questions = []

        # 1. Récupérer les questions existantes (depuis la base de données ou l'entrée)
        existing_questions = input_data.existing_questions or []
        if not existing_questions:
            existing_questions = get_questions_by_document_id(input_data.document_id)

        # 2. Ajouter les questions existantes à la liste
        for q in existing_questions:
            selected_questions.append(
                SelectedQuestion(
                    question_text=q["question_text"],
                    answer_text=q["answer_text"],
                    source=q.get("source", "database")
                )
            )

        # 3. Générer les questions manquantes si nécessaire
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
        Génère de nouvelles questions avec l'agent QA.
        """
        response = self.qa_agent.run({
            "message": f"Génère {num_questions} questions.",
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

def get_question_selector_agent(model: str = "mistral-medium") -> QuestionSelectorAgent:
    """
    Fabrique pour obtenir l'agent de sélection de questions.
    """
    return QuestionSelectorAgent(model)
