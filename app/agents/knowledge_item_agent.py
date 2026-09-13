"""AtomicAgent de génération d'éléments de connaissance (knowledge_items).

Cet agent extrait des propositions factuelles vérifiables depuis un chunk de texte,
et les structure avec leurs entités, thèmes et référence de source, conformément
au schéma défini dans app/database/user_knowledge_model.sql (section 2).

Il suit la convention des autres agents du dépôt (qa_agent, summariser_agent,
message_evaluator_agent) : schemas BaseIOSchema, prompt YAML chargé via
prompt_loader avec un fallback SystemPromptGenerator, client Mistral via
mistral_client.get_mistral_client, factory get_knowledge_item_agent.
"""
from typing import List, Optional, Literal
from pydantic import Field

from atomic_agents import AtomicAgent, AgentConfig, BaseIOSchema
from atomic_agents.context import SystemPromptGenerator, ChatHistory

from .mistral_client import get_mistral_client
from .prompt_loader import get_prompt


# ============================================================================
# SCHÉMAS D'ENTRÉE / SORTIE (BaseIOSchema)
# ============================================================================

EntityTypeLiteral = Literal["person", "place", "work", "event", "practice", "other"]


class EntitySchema(BaseIOSchema):
    """Une entité (personne, lieu, œuvre, événement, pratique) mentionnée
    dans une connaissance. Correspond à la table entities et à la relation
    knowledge_item_entities."""
    name: str = Field(..., description="Nom complet de l'entité")
    type: EntityTypeLiteral = Field(
        default="other",
        description="Type d'entité: person, place, work, event, practice, other"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Confiance dans l'association entité-connaissance (0-1)"
    )


class ThemeSchema(BaseIOSchema):
    """Un thème associé à une connaissance. Correspond à la table themes et
    à la relation knowledge_item_themes."""
    name: str = Field(..., description="Nom du thème")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Confiance dans l'association thème-connaissance (0-1)"
    )


class SourceReferenceSchema(BaseIOSchema):
    """Référence vers la source d'une connaissance (chunk/document).
    Correspond à la table knowledge_sources."""
    document_id: Optional[str] = Field(
        default=None, description="Identifiant du document source"
    )
    chunk_id: Optional[str] = Field(
        default=None, description="Identifiant du chunk source"
    )
    excerpt: str = Field(
        default="",
        description="Extrait exact du texte qui soutient la proposition"
    )
    page: Optional[int] = Field(default=None, description="Numéro de page")
    position_in_page: Optional[int] = Field(
        default=None, description="Position dans la page"
    )
    position_start: int = Field(
        default=0, description="Position de début de l'extrait (indice 0-based)"
    )
    position_end: int = Field(
        default=0, description="Position de fin de l'extrait (indice 0-based)"
    )
    uri: Optional[str] = Field(
        default=None, description="URI spécifique de la source"
    )


class KnowledgeItemSchema(BaseIOSchema):
    """Un élément de connaissance atomique et vérifiable.
    Correspond à la table knowledge_items et à ses relations."""
    proposition: str = Field(
        ..., description="Proposition ou information formulée et vérifiable"
    )
    summary: Optional[str] = Field(
        default=None, description="Résumé ou titre court de la connaissance"
    )
    entities: List[EntitySchema] = Field(
        default_factory=list,
        description="Entités associées (knowledge_item_entities)"
    )
    themes: List[ThemeSchema] = Field(
        default_factory=list,
        description="Thèmes associés (knowledge_item_themes)"
    )
    source_reference: SourceReferenceSchema = Field(
        default_factory=SourceReferenceSchema,
        description="Référence à la source (knowledge_sources)"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Confiance dans cette connaissance (0-1)"
    )
    is_verified: bool = Field(
        default=False, description="La connaissance a-t-elle été vérifiée"
    )
    verification_notes: Optional[str] = Field(
        default=None, description="Notes de vérification"
    )


class KnowledgeExtractionInput(BaseIOSchema):
    """Entrée de l'agent : le texte du chunk à analyser et ses métadonnées
    de localisation (pour alimenter les source_references)."""
    text_chunk: str = Field(..., description="Texte du chunk à analyser")
    chunk_id: Optional[str] = Field(default=None, description="Identifiant du chunk")
    document_id: Optional[str] = Field(default=None, description="Identifiant du document")
    page: Optional[int] = Field(default=None, description="Numéro de page du chunk")
    position_in_page: Optional[int] = Field(
        default=None, description="Position du chunk dans la page"
    )


class KnowledgeExtractionOutput(BaseIOSchema):
    """Sortie de l'agent : la liste des knowledge_items extraits."""
    knowledge_items: List[KnowledgeItemSchema] = Field(
        default_factory=list,
        description="Liste des éléments de connaissance extraits"
    )


# ============================================================================
# PROMPT SYSTÈME (fallback)
# ============================================================================

_FALLBACK_PROMPT = SystemPromptGenerator(
    background=[
        "Tu es un expert en extraction d'éléments de connaissance depuis des textes.",
        "Ton objectif est d'identifier des propositions atomiques et vérifiables, "
        "puis de les relier à des entités, thèmes et sources.",
        "Travaille EXCLUSIVEMENT en FRANÇAIS.",
        "Sois précis, rigoureux et méthodique. Ne devine pas, "
        "extrait uniquement ce qui est présent dans le texte.",
    ],
    steps=[
        "Lis attentivement le texte fourni dans son intégralité",
        "Identifie TOUTES les PROPOSITIONS FACTUELLES VÉRIFIABLES "
        "(une affirmation précise qui peut être vraie ou fausse)",
        "Pour chaque proposition identifiée:",
        "  1. Extrait la proposition exacte dans 'proposition' "
        "(doit être une phrase complète et compréhensible)",
        "  2. Crée un résumé très court (5-15 mots) dans 'summary'",
        "  3. Identifie TOUTES les entités mentionnées avec leur type "
        "et confiance dans 'entities'",
        "  4. Identifie TOUS les thèmes principaux abordés avec "
        "confiance dans 'themes'",
        "  5. Note l'extrait EXACT du texte qui soutient cette proposition "
        "avec positions de début et fin dans 'source_reference'",
        "Élimine les propositions trop vagues, subjectives ou non vérifiables",
    ],
    output_instructions=[
        "Chaque 'proposition' DOIT être une affirmation factuelle vérifiable "
        "(pas de questions, pas d'opinions, pas de descriptions générales)",
        "Les positions (position_start, position_end) DOIVENT correspondre "
        "exactement à l'emplacement de la proposition dans le texte source "
        "(indices 0-based)",
        "Les entités DOIVENT être des noms propres ou concepts bien définis "
        "(ex: 'Léonard de Vinci', 'Musée du Louvre', pas 'un homme')",
        "Les thèmes DOIVENT être des catégories générales et précises "
        "(ex: 'Histoire de France', 'Technique de peinture à l'huile')",
        "Le champ 'excerpt' DOIT contenir le passage exact du texte "
        "qui soutient la proposition",
        "Si une information n'est pas certaine dans le texte, "
        "utilise une confiance entre 0.5 et 0.7",
        "Ne pas inventer d'informations non présentes dans le texte",
        "Pour les entités, utilise des noms COMPLETS et PRÉCIS "
        "(ex: 'Léonard de Vinci' et non 'Léonard')",
        "Si le texte ne contient aucune proposition factuelle vérifiable, "
        "retourne une liste vide",
    ],
)


def _load_system_prompt(prompt_name: str = "default") -> SystemPromptGenerator:
    """Charge le prompt système depuis le YAML knowledge_item.yaml,
    avec le fallback si le fichier est absent ou le prompt introuvable."""
    loaded = get_prompt("knowledge_item", prompt_name)
    return loaded if loaded is not None else _FALLBACK_PROMPT


# ============================================================================
# FACTORY
# ============================================================================

def get_knowledge_item_agent(
    model: str = "mistral-medium",
    async_mode: bool = True,
    prompt_name: str = "default",
) -> AtomicAgent:
    """Crée et retourne un AtomicAgent de génération de knowledge_items.

    Args:
        model: Nom du modèle LLM à utiliser (par défaut: mistral-medium).
        async_mode: Si True, le client Mistral est asynchrone (run_async).
        prompt_name: Nom du prompt à charger depuis knowledge_item.yaml
                     ("default" ou "compact").

    Returns:
        AtomicAgent[KnowledgeExtractionInput, KnowledgeExtractionOutput]
        configuré pour l'extraction de connaissances.
    """
    client = get_mistral_client(async_mode=async_mode)
    system_prompt_generator = _load_system_prompt(prompt_name)

    agent = AtomicAgent[KnowledgeExtractionInput, KnowledgeExtractionOutput](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=system_prompt_generator,
        )
    )
    return agent


# ============================================================================
# FONCTION D'APPEL DE HAUT NIVEAU
# ============================================================================

async def generate_knowledge_items_from_chunk(
    text: str,
    chunk_id: Optional[str] = None,
    document_id: Optional[str] = None,
    page: Optional[int] = None,
    position_in_page: Optional[int] = None,
    model: str = "mistral-medium",
    prompt_name: str = "default",
) -> List[KnowledgeItemSchema]:
    """Génère des knowledge_items à partir d'un chunk de texte via l'agent.

    Args:
        text: Texte du chunk à analyser.
        chunk_id: Identifiant du chunk.
        document_id: Identifiant du document.
        page: Numéro de page du chunk.
        position_in_page: Position du chunk dans la page.
        model: Modèle LLM à utiliser.
        prompt_name: Prompt à utiliser ("default" ou "compact").

    Returns:
        Liste de KnowledgeItemSchema extraits.
    """
    if not text or not text.strip():
        return []

    agent = get_knowledge_item_agent(model=model, async_mode=True, prompt_name=prompt_name)

    input_data = KnowledgeExtractionInput(
        text_chunk=text,
        chunk_id=chunk_id,
        document_id=document_id,
        page=page,
        position_in_page=position_in_page,
    )

    result = await agent.run_async(input_data)
    return result.knowledge_items or []
