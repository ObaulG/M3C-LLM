# agents/session_question_agent.py
"""
Agent de composition automatique d'une session de questions.

À partir des instructions du médiateur culturel/scientifique, l'agent propose une
liste de questions pour la session :
- "existing" : une question existante (en base) correspondant à la demande,
- "adapted"  : une question inspirée d'une existante, mais reformulée (question et réponse modifiées),
- "new"      : une paire question/réponse créée directement.

Important : cet agent ne sauvegarde rien en base de données. Il retourne uniquement
des propositions, que l'utilisateur peut ensuite négocier puis valider avec la session.
"""
from typing import List, Literal, Optional

from atomic_agents import AtomicAgent, AgentConfig, BaseIOSchema
from atomic_agents.context import SystemPromptGenerator
import instructor

from .instructor_factory import create_client
from .prompt_loader import get_prompt


class SessionQuestionGenerationInput(BaseIOSchema):
    """
    Entrée de l'agent de composition de session.

    - mediator_instructions : ce que le médiateur cherche à présenter au visiteur.
    - num_questions : nombre de propositions attendu.
    - candidate_questions : questions existantes du document (id, contenu, réponse de référence).
    - current_proposals : propositions retenues lors d'une négociation en cours (optionnel).
    - negotiation_instructions : consignes de négociation de l'utilisateur (optionnel).
    """
    mediator_instructions: str
    num_questions: int
    candidate_questions: List[dict] = []
    current_proposals: Optional[List[dict]] = None
    negotiation_instructions: Optional[str] = None


class SessionQuestionProposal(BaseIOSchema):
    """
    Une proposition de question pour la session.

    - proposal_type "existing" : question existante reprise telle quelle (source_question_id requis).
    - proposal_type "adapted"  : reformulation d'une question existante (source_question_id = origine).
    - proposal_type "new"      : question créée pour l'occasion (source_question_id = null).
    """
    question: str
    answer: str = ""
    proposal_type: Literal["existing", "adapted", "new"] = "new"
    source_question_id: Optional[int] = None
    rationale: str = ""


class SessionQuestionProposalsOutput(BaseIOSchema):
    """Liste des propositions de questions pour la session (sans sauvegarde en BDD)."""
    proposals: List[SessionQuestionProposal]
    summary: str = ""


# Fallback si le fichier YAML est indisponible
_FALLBACK_PROMPT = SystemPromptGenerator(
    background=[
        "Tu composes une session de questions à partir des instructions d'un médiateur et d'une liste de questions existantes.",
        "Tu privilégies les questions existantes, puis les adaptations, puis les créations de nouvelles paires question/réponse.",
    ],
    steps=[
        "Analyser les instructions du médiateur.",
        "Sélectionner en priorité les questions existantes correspondantes.",
        "Adapter ou créer les questions manquantes.",
        "En cas de négociation, appliquer les consignes sur les propositions retenues.",
    ],
    output_instructions=[
        "Retourner exactement le nombre de questions demandé.",
        "proposal_type parmi 'existing', 'adapted', 'new'.",
        "source_question_id doit être un identifiant de la liste des candidats (ou null pour 'new').",
        "Questions et réponses en français.",
    ],
)


def get_session_question_agent(model: str = "mistral-small-2603",
                               provider: str = "mistral",
                               async_mode: bool = True):
    """
    Crée l'agent de composition de session de questions.

    Args:
        model: Nom du modèle LLM.
        provider: Fournisseur ("mistral", "ollama", "google").
        async_mode: Si True, retourne un agent asynchrone (run_async).
    """
    client = create_client(provider, model, async_mode=async_mode, instructor_mode=instructor.Mode.JSON)
    system_prompt_generator = get_prompt("session_question", "default") or _FALLBACK_PROMPT
    agent = AtomicAgent[SessionQuestionGenerationInput, SessionQuestionProposalsOutput](
        config=AgentConfig(
            client=client,
            model=model,
            history=None,
            tools=None,
            system_prompt_generator=system_prompt_generator,
        )
    )
    return agent
