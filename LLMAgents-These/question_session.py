# services/session_service.py
from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel

class QuestionAnswer(BaseModel):
    question_text: str
    answer_text: str

class QuestionAnswerList(BaseModel):
    questions_answers: List[QuestionAnswer]

class EvaluateRequest(BaseModel):
    question: str
    expected_answer: str
    user_answer: str

class EvaluationResult(BaseModel):
    score: int
    feedback: str
    cosine_similarity: float

class UserResponse(BaseModel):
    question: str
    expected_answer: str
    user_answer: str
    score: int
    feedback: str
    cosine_similarity: float
    timestamp: str

class SessionResponse(BaseModel):
    session_id: str
    document_id: str
    responses: List[UserResponse]
    completed: bool

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}

    def create_session(self, session_id: str, document_id: str):
        """Crée une nouvelle session."""
        self.sessions[session_id] = {
            "document_id": document_id,
            "questions": [],
            "responses": [],
            "completed": False,
            "created_at": datetime.now().isoformat(),
        }

    def add_questions(self, session_id: str, questions: List):
        """Ajoute les questions générées à une session."""
        if session_id in self.sessions:
            self.sessions[session_id]["questions"] = questions

    def add_response(self, session_id: str, response: UserResponse):
        """Ajoute une réponse utilisateur à une session."""
        if session_id in self.sessions:
            self.sessions[session_id]["responses"].append(response)

    def get_session(self, session_id: str) -> Dict:
        """Récupère une session."""
        return self.sessions.get(session_id)

    def mark_as_completed(self, session_id: str):
        """Marque une session comme terminée."""
        if session_id in self.sessions:
            self.sessions[session_id]["completed"] = True
