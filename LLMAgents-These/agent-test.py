from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mistralai import ChatMistralAI
import json
import os
from typing import Dict, List, Optional

# Initialisation du LLM (ex: Mistral)
llm = ChatMistralAI(model="mistral-tiny", api_key=os.getenv("MISTRAL_API_KEY"))

# État global de la session
class SessionState:
    def __init__(self):
        self.questions: List[Dict] = []  # Liste des questions/réponses
        self.current_question_index: int = 0
        self.user_responses: List[Dict] = []  # Historique des réponses utilisateur

state = SessionState()

# Agent 1 : Analyse le document et génère des questions/réponses
def question_answer_generation(document_text: str,
                               n_questions: int) -> List[Dict]:
    prompt = f"""
Tu es un assistant pédagogique spécialisé dans la compréhension de textes.
À partir du texte suivant, génère exactement {n_questions} questions en français,
accompagnées chacune de leur réponse courte, basée uniquement sur le texte.

Texte :
\"\"\"{document_text}\"\"\"

Contraintes importantes :
- Les questions doivent être compréhensives (pas triviales, pas hors sujet).
- Les réponses doivent être directement justifiées par le texte.
- Si une information n'est pas clairement présente, ne l'invente pas : adapte la question.
- Les questions et réponses doivent être en français.

FORMAT DE SORTIE STRICT :
Réponds UNIQUEMENT avec un JSON valide de la forme :

{{
  "qas": [
    {{
      "question": "…",
      "answer": "…"
    }},
    {{
      "question": "…",
      "answer": "…"
    }}
  ]
}}

Ne mets aucun texte avant ou après le JSON.
"""
    response = llm.invoke([HumanMessage(content=prompt)])
    questions = json.loads(response.content)
    state.questions = questions
    return questions

# Agent 2 : Pose une question et évalue la réponse
def tutor(user_response: str) -> Dict:
    if not state.questions:
        return {"error": "Aucune question générée. Veuillez d'abord analyser un document."}

    current_question = state.questions[state.current_question_index]
    expected_answer = current_question["answer"]

    # Évaluation de la réponse
    evaluation_prompt = f"""
    Évalue la réponse de l'utilisateur par rapport à la réponse attendue.
    - Réponse attendue : {expected_answer}
    - Réponse utilisateur : {user_response}
    Retourne un dictionnaire avec :
    - "feedback" (str) : un feedback constructif
    - "score" (float) : un score entre 0 et 1
    """
    evaluation = llm.invoke([HumanMessage(content=evaluation_prompt)])
    evaluation_result = json.loads(evaluation.content)

    # Mise à jour de l'état
    state.user_responses.append({
        "question": current_question["question"],
        "user_response": user_response,
        "feedback": evaluation_result["feedback"],
        "score": evaluation_result["score"]
    })
    state.current_question_index += 1

    return evaluation_result

# Agent 3 : Gère l'état (ex: réinitialisation, affichage de l'historique)
def state_manager(command: str) -> Dict:
    if command == "reset":
        state.questions = []
        state.current_question_index = 0
        state.user_responses = []
        return {"status": "Session réinitialisée"}
    elif command == "history":
        return {"history": state.user_responses}
    else:
        return {"error": "Commande inconnue"}


# Définition du graphe LangGraph
workflow = StateGraph(MessagesState)

# Ajout des nœuds (agents)
workflow.add_node("analyzer", document_analyzer)
workflow.add_node("tutor", tutor)
workflow.add_node("state_manager", state_manager)

# Définition des transitions
workflow.add_edge("analyzer", "tutor")
workflow.add_edge("tutor", "state_manager")

# Point d'entrée
workflow.set_entry_point("analyzer")

# Compilation du graphe
app = workflow.compile()
