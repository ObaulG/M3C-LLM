# services/session_service.py
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel

from agents.answer_evaluator_agent import AgentEvaluationResult

# Suite de questions prédéfinies pour des fins de démonstration
PREMADE_QUESTIONS_BY_DOCUMENT_ID = {
    "dbd5f14a9e6545880b0cd505583ea7d1fe1e8b3d" : [249, 370, 737, 786, 115],
    #"8a672d2ae6f2abfa4434e0f4145a9aa77bbc6d56" : [2021, 1224, 1506, 1525, 1757]
    "8a672d2ae6f2abfa4434e0f4145a9aa77bbc6d56" : [9158, 9235, 9389, 10040, ]
}

class SessionMetadata(BaseModel):
    """
    Contient les données techniques décrivant une sesssion : la méthode d'évaluation,
    les LLM utilisés et leur agencement.
    """
    llm_evaluators_model: str
    nb_evaluators: int
    with_final_evaluator: bool
    llm_final_model: Optional[str]


class QuestionAnswer(BaseModel):
    """Représente une paire question-réponse.

    Cette classe modélise une question et sa réponse associée.

    Attributes:
        question_text (str): Le texte de la question posée.
        answer_text (str): Le texte de la réponse correspondante.
    """
    question_text: str
    answer_text: str

class QuestionAnswerList(BaseModel):
    questions_answers: List[QuestionAnswer]

class EvaluateRequest(BaseModel):
    """
    Représente une requête d'évaluation contenant une question, la réponse attendue et la réponse de l'utilisateur.

    Attributes:
        question (str): Le texte de la question posée.
        expected_answer (str): La réponse attendue.
        user_answer (str): La réponse fournie par l'utilisateur à évaluer.
    """
    question: str
    expected_answer: str
    user_answer: str

class EvaluationResult(BaseModel):
    """
    Représente le résultat de l'évaluation d'une réponse par un modèle de langage.
    Utilisé dans UserResponse qui référence l'id de la question et son texte.
    Attention, différent du EvaluationResult de answer_evaluator_agent.py,
    qui hérite de BaseIOModel, prévu pour fonctionner avec AtomicAgents;
    """
    score: int
    feedback: str
    model: Optional[str]

class UserResponse(BaseModel):
    """
    Représente les données d'une réponse donnée à une question par un utilisateur.
    Si l'évaluation n'a pas été faite, alors elle n'est pas renseignée.
    """
    question_id: int
    question_text: str
    user_answer: str
    date_sent: datetime
    evaluation: Optional[EvaluationResult]

class SessionStatus(BaseModel):
    """
    Représente l'état global d'une session d'un utilisateur.
    """
    session_id: str
    document_id: str
    current_index: int
    completed: bool
    created_at: datetime
    time_elapsed_secs: int
    responses: List[UserResponse]
    questions_ids: List[int]
    questions_text: List[str]
    pages: List[int]

def from_AgentEvaluationResult_to_EvaluationResult(evaluation: AgentEvaluationResult,
                                                   model: Optional[str] = None) -> EvaluationResult:
    return EvaluationResult(
        score= evaluation.score,
        feedback=evaluation.feedback,
        model=model,
    )

import json
from datetime import datetime
from typing import Dict, Any

def session_status_to_dict(session_status: SessionStatus) -> Dict[str, Any]:
    """
    Convertit un objet SessionStatus en dictionnaire pour la sérialisation JSON.
    """
    def serialize_evaluation_result(evaluation: EvaluationResult) -> Dict[str, Any]:
        if evaluation is None:
            return None
        return {
            "score": evaluation.score,
            "feedback": evaluation.feedback,
            "cosine_similarity": evaluation.cosine_similarity,
            "model": evaluation.model,
        }

    def serialize_user_response(response: UserResponse) -> Dict[str, Any]:
        return {
            "question_id": response.question_id,
            "question_text": response.question_text,
            "user_answer": response.user_answer,
            "date_sent": response.date_sent.isoformat(),
            "evaluation": serialize_evaluation_result(response.evaluation),
        }

    return {
        "session_id": session_status.session_id,
        "document_id": session_status.document_id,
        "current_index": session_status.current_index,
        "completed": session_status.completed,
        "created_at": session_status.created_at.isoformat(),
        "time_elapsed_secs": session_status.time_elapsed_secs,
        "responses": [serialize_user_response(r) for r in session_status.responses],
        "questions_ids": session_status.questions_ids,
        "questions_text": session_status.questions_text,
        "pages": session_status.pages,
    }

def export_session_status_to_json(session_status: SessionStatus, file_path: str = None) -> str:
    """
    Exporte un SessionStatus en JSON, soit dans un fichier, soit retourne la chaîne JSON.

    Args:
        session_status: L'objet SessionStatus à exporter.
        file_path: Chemin optionnel pour sauvegarder le JSON dans un fichier.
                   Si None, retourne la chaîne JSON.

    Returns:
        str: La chaîne JSON si file_path est None, sinon None.
    """
    data = session_status_to_dict(session_status)
    json_str = json.dumps(data, indent=2, ensure_ascii=False)

    if file_path:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(json_str)
        return None
    else:
        return json_str


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}

    def create_session(self,
                       document_id: str,
                       premade_session: bool = False) -> str:
        """
        Crée une nouvelle session utilisateur, en générant un session_id,
        qui sera retourné pour pouvoir l'utiliser (ajout direct de questions).
        """

        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "document_id": document_id,
            "questions_ids": [],
            "questions_text": [],
            "pages": [],
            "responses": [],
            "current_index": 0,
            "completed": False,
            "created_at": datetime.now(),
            "premade": premade_session,
        }
        return session_id

    def add_questions(self,
                      session_id: str,
                      questions_ids: list[int],
                      questions_texts: list[str],
                      questions_pages: list[str]):
        """Ajoute les questions générées à une session."""

        if session_id in self.sessions:
            self.sessions[session_id]["questions_ids"].extend(questions_ids)
            self.sessions[session_id]["questions_text"].extend(questions_texts)
            self.sessions[session_id]["pages"].extend(questions_pages)

    def add_response(self, session_id: str, response: UserResponse):
        """Ajoute une réponse utilisateur à une session."""
        if session_id in self.sessions:
            self.sessions[session_id]["responses"].append(response)

    def mark_session_as_completed(self, session_id: str):
        """Marque une session comme terminée."""
        if session_id in self.sessions:
            self.sessions[session_id]["completed"] = True

    def increment_current_index(self, session_id: str):
        if session_id in self.sessions:
            # si on incrémente alors qu'on est déjà au dernier élément, la session peut-être marquée comme terminée
            if self.sessions[session_id]["current_index"] == len(self.sessions[session_id]["questions_ids"])-1:
                self.mark_session_as_completed(session_id)
            else:
                self.sessions[session_id]["current_index"] += 1

    def get_session(self, session_id: str) -> Dict:
        """Récupère une session."""
        return self.sessions.get(session_id)

    def get_session_status(self, session_id: str) -> SessionStatus:
        time_elapsed = datetime.now() - self.sessions[session_id]["created_at"]
        time_elapsed_secs = int(time_elapsed.total_seconds())

        return SessionStatus(
            session_id=session_id,
            document_id=self.sessions[session_id]["document_id"],
            current_index=self.sessions[session_id]["current_index"],
            completed=self.sessions[session_id]["completed"],
            created_at=self.sessions[session_id]["created_at"],
            time_elapsed_secs=time_elapsed_secs,
            questions_ids=self.sessions[session_id]["questions_ids"],
            questions_text=self.sessions[session_id]["questions_text"],
            pages=self.sessions[session_id]["pages"],
            responses=self.sessions[session_id]["responses"],
        )

    def get_current_question_id(self, session_id: str) -> int:
        index = self.sessions[session_id]["current_index"]
        return self.sessions[session_id]["questions_ids"][index]

    def get_current_question_text(self, session_id: str) -> str:
        index = self.sessions[session_id]["current_index"]
        return self.sessions[session_id]["questions_text"][index]

    def is_finished(self, session_id: str) -> bool:
        return self.sessions[session_id]["completed"]