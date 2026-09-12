from typing import List, Optional
from atomic_agents import BaseIOSchema, AtomicAgent, AgentConfig
from atomic_agents.context import SystemPromptGenerator, ChatHistory
from pydantic import Field

from .mistral_client import get_mistral_client

# Note: 03/02/26, difficultées rencontrées avec le structured output.
# ChunkSummaryRequestInput était parfois renommé ChunkSummarySummaryInput,
# ce qui faisait planter l'exécution des tests.

class ChunkSummaryRequestInput(BaseIOSchema):
    """

    Contains the text of the chunk to be summarized.
    """
    chunk_text: str = Field(
        ...,
        description="The text of the chunk to be summarized by the agent."
    )

class ChunkSummaryResult(BaseIOSchema):
    """
    Contains the summary of a chunk.
    """
    summary: str = Field(
        ...,
        description="The generated summary of the chunk."
    )

class MergeSummariesRequestInput(BaseIOSchema):
    """
    Schema for the input of the summaries merging agent.
    Contains the summaries to merge and optional additional context.
    """
    summaries: List[str] = Field(
        ...,
        description="List of summaries to be merged."
    )
    context: Optional[str] = Field(
        default=None,
        description="Optional additional context (e.g., previous summary)."
    )

class MergedSummaryResult(BaseIOSchema):
    """
    Contains the merged summary result.
    """
    merged_summary: str = Field(
        ...,
        description="The merged summary generated from multiple summaries."
    )

class ArtifactRemovalRequestInput(BaseIOSchema):
    """
    Schema for the input text to be processed for artifact removal.
    """
    input_text: str = Field(
        ...,
        description="The input text to be processed for artifact removal."
    )

class ArtifactRemovalResult(BaseIOSchema):
    """
    Contains the processed text after artifact removal.
    """
    result_text: str = Field(
        ...,
        description="The processed text with artifacts removed."
    )

def get_chunk_summariser_agent(model: str = "mistral-medium", max_words: int = 100):
    client = get_mistral_client()
    return AtomicAgent[ChunkSummaryRequestInput, ChunkSummaryResult](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=SystemPromptGenerator(
                background=[
                    "Vous êtes un expert en résumé de documents. Votre tâche consiste à résumer un morceau de texte (chunk) en un paragraphe concis, tout en capturant les informations essentielles."
                ],
                steps=[
                    "Lire attentivement le texte fourni.",
                    "Identifier les idées principales, les événements clés, les lieux, les personnages (le cas échéant), et les informations contextuelles importantes.",
                    "Rédiger un résumé clair et structuré en français, en mettant l'accent sur les éléments pertinents pour comprendre la Corse.",
                    "Si le chunk introduit des éléments pour la première fois (ex: un lieu, une tradition), les présenter brièvement.",
                ],
                output_instructions=[
                    "Le résumé doit être concis, rédigé en phrases complètes, sans liste à puces.",
                    f"Maximum {max_words} mots",
                    "Éviter les phrases comme 'dans ce chunk' ou 'dans cette partie'. Le résumé doit sembler cohérent et autonome.",
                ],
            ),
        )
    )

def get_summaries_merger_agent(model: str = "mistral-medium", max_words: int = 100):
    client = get_mistral_client()
    return AtomicAgent[MergeSummariesRequestInput, MergedSummaryResult](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=SystemPromptGenerator(
    background=[
        "Vous êtes un expert en synthèse de documents. On cherche à résumer de manière récursive un document en résumant des morceaux de documents.",
        "Les résumés proviennent d'un document long, et doivent être combinés pour former un résumé global.",
    ],
    steps=[
        "Lire attentivement tous les résumés fournis.",
        "Identifier les idées principales, les thèmes communs, et les informations clés à conserver.",
        "Fusionner les résumés en un seul texte cohérent, en organisant les informations de manière logique (par exemple, par thème ou chronologie).",
        "Éviter les répétitions et privilégier les informations les plus pertinentes.",
    ],
    output_instructions=[
        "Le résumé fusionné doit être clair, structuré, fluide et inclure les idées principales de tous les résumés fournis.",
        f"Maximum {max_words} mots",
        "Éviter les phrases comme 'dans le premier résumé' ou 'dans le chunk précédent'. Le résumé doit sembler écrit d'un seul tenant.",
    ],
),
        )
    )

def get_context_summaries_merger_agent(model: str = "mistral-medium", max_words: int = 100):
    client = get_mistral_client()
    return AtomicAgent[MergeSummariesRequestInput, MergedSummaryResult](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=SystemPromptGenerator(
    background=[
        "Vous êtes un expert en synthèse de documents. On cherche à résumer de manière récursive un document en résumant des morceaux de documents.",
        "Le contexte précédent et les résumés proviennent d'un document.",
    ],
    steps=[
        "Lire attentivement le contexte précédent et les résumés fournis.",
        "Identifier les informations clés dans le contexte et les résumés.",
        "Fusionner le contexte et les résumés en un seul texte cohérent, en organisant les informations de manière logique.",
        "Assurer la continuité entre le contexte et les nouveaux résumés.",
    ],
    output_instructions=[
        "Le résumé fusionné doit être clair, structuré, fluide et inclure les idées principales de tous les résumés fournis.",
        f"Maximum {max_words} mots",
        "Éviter les phrases comme 'dans le contexte précédent' ou 'dans les résumés suivants'. Le résumé doit sembler écrit d'un seul tenant.",
    ],
),
        )
    )

def get_artifact_removal_prompt_generator(model: str = "mistral-medium"):
    client = get_mistral_client()
    return AtomicAgent[ArtifactRemovalRequestInput, ArtifactRemovalResult](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=SystemPromptGenerator(
    background=[
        "Votre tâche consiste à nettoyer un résumé pour qu'il semble avoir été écrit en une seule fois.",
        "Le résumé a été généré en plusieurs étapes, et peut contenir des artefacts de ce processus.",
    ],
    steps=[
        "Lire attentivement le résumé fourni.",
        "Supprimer toutes les phrases qui indiquent que le résumé a été développé progressivement (ex: 'dans cette partie', 'dans le chunk précédent').",
        "Supprimer toute information qui ne fait pas partie du contenu principal (ex: table des matières, remerciements, biographie de l'auteur).",
    ],
    output_instructions=[
        "Le résumé nettoyé doit sembler naturel et cohérent.",
        "Ne pas ajouter ou modifier d'informations, seulement supprimer les artefacts.",
        "Le résumé doit être fluide et facile à lire.",
    ],
),
        )
    )