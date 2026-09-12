from typing import List, Optional
from atomic_agents import BaseIOSchema, AtomicAgent, AgentConfig
from atomic_agents.context import SystemPromptGenerator, ChatHistory
from pydantic import Field

from .mistral_client import get_mistral_client
from .prompt_loader import get_prompt

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
    loaded = get_prompt("summariser", "chunk_summariser", max_words=max_words)
    fallback = SystemPromptGenerator(
        background=[
            "Vous etes un expert en resume de documents. Votre tache consiste a resumer un morceau de texte (chunk) en un paragraphe concis, tout en capturant les informations essentielles."
        ],
        steps=[
            "Lire attentivement le texte fourni.",
            "Identifier les idees principales, les evenements cles, les lieux, les personnages (le cas echeant), et les informations contextuelles importantes.",
            "Rediger un resume clair et structure en francais, en mettant l'accent sur les elements pertinents pour comprendre la Corse.",
            "Si le chunk introduit des elements pour la premiere fois (ex: un lieu, une tradition), les presenter brièvement.",
        ],
        output_instructions=[
            "Le resume doit etre concis, redige en phrases complete, sans liste a puces.",
            f"Maximum {max_words} mots",
            "Eviter les phrases comme dans ce chunk ou dans cette partie. Le resume doit sembler coherent et autonome.",
        ],
    )
    return AtomicAgent[ChunkSummaryRequestInput, ChunkSummaryResult](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=loaded if loaded is not None else fallback,
        )
    )


def get_summaries_merger_agent(model: str = "mistral-medium", max_words: int = 100):
    client = get_mistral_client()
    loaded = get_prompt("summariser", "summaries_merger", max_words=max_words)
    fallback = SystemPromptGenerator(
        background=[
            "Vous etes un expert en synthese de documents. On cherche a resumer de maniere recursive un document en resumant des morceaux de documents.",
            "Les resumes proviennent d'un document long, et doivent etre combines pour former un resume global.",
        ],
        steps=[
            "Lire attentivement tous les resumes fournis.",
            "Identifier les idees principales, les themes communs, et les informations cles a conserver.",
            "Fusionner les resumes en un seul texte coherent, en organisant les informations de maniere logique (par exemple, par theme ou chronologie).",
            "Eviter les repetitions et privilegie les informations les plus pertinentes.",
        ],
        output_instructions=[
            "Le resume fusionne doit etre clair, structure, fluide et inclure les idees principales de tous les resumes fournis.",
            f"Maximum {max_words} mots",
            "Eviter les phrases comme dans le premier resume ou dans le chunk precedent. Le resume doit sembler ecrit d'un seul tenant.",
        ],
    )
    return AtomicAgent[MergeSummariesRequestInput, MergedSummaryResult](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=loaded if loaded is not None else fallback,
        )
    )


def get_context_summaries_merger_agent(model: str = "mistral-medium", max_words: int = 100):
    client = get_mistral_client()
    loaded = get_prompt("summariser", "context_summaries_merger", max_words=max_words)
    fallback = SystemPromptGenerator(
        background=[
            "Vous etes un expert en synthese de documents. On cherche a resumer de maniere recursive un document en resumant des morceaux de documents.",
            "Le contexte precedent et les resumes proviennent d'un document.",
        ],
        steps=[
            "Lire attentivement le contexte precedent et les resumes fournis.",
            "Identifier les informations cles dans le contexte et les resumes.",
            "Fusionner le contexte et les resumes en un seul texte coherent, en organisant les informations de maniere logique.",
            "Assurer la continuite entre le contexte et les nouveaux resumes.",
        ],
        output_instructions=[
            "Le resume fusionne doit etre clair, structure, fluide et inclure les idees principales de tous les resumes fournis.",
            f"Maximum {max_words} mots",
            "Eviter les phrases comme dans le contexte precedent ou dans les resumes suivants. Le resume doit sembler ecrit d'un seul tenant.",
        ],
    )
    return AtomicAgent[MergeSummariesRequestInput, MergedSummaryResult](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=loaded if loaded is not None else fallback,
        )
    )


def get_artifact_removal_prompt_generator(model: str = "mistral-medium"):
    client = get_mistral_client()
    loaded = get_prompt("summariser", "artifact_removal")
    fallback = SystemPromptGenerator(
        background=[
            "Votre tache consiste a nettoyer un resume pour qu'il semble avoir ete ecrit en une seule fois.",
            "Le resume a ete genere en plusieurs etapes, et peut contenir des artefacts de ce processus.",
        ],
        steps=[
            "Lire attentivement le resume fourni.",
            "Supprimer toutes les phrases qui indiquent que le resume a ete developpe progressivement (ex: dans cette partie, dans le chunk precedent).",
            "Supprimer toute information qui ne fait pas partie du contenu principal (ex: table des matieres, remerciements, biographie de l'auteur).",
        ],
        output_instructions=[
            "Le resume nettoye doit sembler naturel et coherent.",
            "Ne pas ajouter ou modifier d'informations, seulement supprimer les artefacts.",
            "Le resume doit etre fluide et facile a lire.",
        ],
    )
    return AtomicAgent[ArtifactRemovalRequestInput, ArtifactRemovalResult](
        config=AgentConfig(
            client=client,
            model=model,
            history=ChatHistory(),
            system_prompt_generator=loaded if loaded is not None else fallback,
        )
    )
