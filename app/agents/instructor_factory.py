import os
import functools
from typing import Union, Literal, Optional
import instructor
from instructor import Instructor, AsyncInstructor
from mistralai import Mistral
from fastapi import HTTPException
from openai import OpenAI, AsyncOpenAI
from google import genai
from google.genai import types

MISTRAL_MODELS = [
    "ministral-3b-2512", "ministral-8b-2512", "ministral-14b-2512",
    "mistral-small-2603", "mistral-large-4"
]
GOOGLE_MODELS = ["gemini-3.5-flash-lite"]
OLLAMA_MODELS = ["ministral-3:3b", "mistral:7b",
                 "gouranshitera/bloom-1b1", "gouranshitera/bloomz-1b7",
                 "gemma4:e2b",
                 "llama3.2:1b", "llama3.2:3b",
                 "qwen3.5:0.8b", "qwen3.5:2b", "qwen3.5:4b"]

def create_client(
    provider: Literal["mistral", "ollama", "google"],
    model: Optional[str],
    async_mode: bool = False,
    extra_body: dict = {},
    instructor_mode: instructor.Mode = instructor.Mode.TOOLS,
) -> Union[Instructor, AsyncInstructor]:
    """
    Crée et retourne un client configuré avec Instructor.

    Args:
        provider: Le fournisseur de modèle ("mistral" ou "ollama").
        model: Le nom du modèle (obligatoire pour google).
        async_mode: Si True, retourne un client asynchrone.
        extra_body: paramètres complémentaires indiqués à la création du client.
    Returns:
        Une instance de Instructor ou AsyncInstructor.

    Raises:
        HTTPException: Si la configuration est invalide.
    """


    if provider == "mistral":
        if instructor_mode == instructor.Mode.TOOLS:
            instructor_mode = instructor.Mode.MISTRAL_TOOLS
        elif instructor_mode == instructor.Mode.JSON:
            instructor_mode = instructor.Mode.MISTRAL_STRUCTURED_OUTPUTS
        return _create_mistral_client(async_mode, instructor_mode)
    elif provider == "ollama":
        return _create_ollama_client(async_mode, extra_body, instructor_mode)
    elif provider == "google" or provider == "gemini":
        if instructor_mode == instructor.Mode.JSON:
            instructor_mode = instructor.Mode.GENAI_STRUCTURED_OUTPUTS
        return _create_gemma_client(async_mode, instructor_mode)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Fournisseur inconnu: {provider}. Utilisez 'mistral' ou 'ollama'."
        )

def _create_gemma_client(
    async_mode: bool,
    instructor_mode: instructor.Mode = instructor.Mode.GENAI_STRUCTURED_OUTPUTS,
) -> Union[Instructor, AsyncInstructor]:
    google_api_key = os.environ.get("GEMINI_API_KEY")

    if not google_api_key:
        raise HTTPException(
            status_code=500,
            detail="La clé API Google n'est pas définie.",
        )

    client = genai.Client(api_key=google_api_key)

    return instructor.from_genai(
        client=client,
        mode=instructor_mode,
        use_async=async_mode,
    )

def _flatten_reasoning_content(completion):
    """
    Aplatit le contenu des réponses des modèles de raisonnement Mistral
    (ex. mistral-large-4), qui renvoient message.content sous forme de liste
    de chunks (ThinkChunk/TextChunk) au lieu d'une chaîne unique.

    Conserve uniquement les chunks de type texte (le "thinking" est exclu),
    faute de quoi la validation JSON d'Instructor échoue avec une erreur
    json_type (input_type=list).
    """
    for choice in getattr(completion, "choices", None) or []:
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        if not isinstance(content, list):
            continue
        parts = []
        for chunk in content:
            if isinstance(chunk, dict):
                chunk_type = chunk.get("type")
                chunk_text = chunk.get("text")
            else:
                chunk_type = getattr(chunk, "type", None)
                chunk_text = getattr(chunk, "text", None)
            if chunk_type == "text" and isinstance(chunk_text, str):
                parts.append(chunk_text)
        message.content = "".join(parts)
    return completion


def _patch_mistral_completions(client, async_mode: bool = False):
    """
    Enveloppe les méthodes de complétion du SDK Mistral réellement appelées
    par Instructor (chat.complete / chat.complete_async, ainsi que
    chat.completions.create) pour aplatir systématiquement le contenu des
    réponses avant qu'Instructor ne les valide.
    """
    chat = client.chat

    original_complete = chat.complete
    original_complete_async = chat.complete_async

    @functools.wraps(original_complete)
    def complete(*args, **kwargs):
        return _flatten_reasoning_content(original_complete(*args, **kwargs))

    @functools.wraps(original_complete_async)
    async def complete_async(*args, **kwargs):
        return _flatten_reasoning_content(await original_complete_async(*args, **kwargs))

    for name, fn in (("complete", complete), ("complete_async", complete_async)):
        try:
            setattr(chat, name, fn)
        except AttributeError:
            object.__setattr__(chat, name, fn)

    completions = getattr(chat, "completions", None)
    if completions is not None and hasattr(completions, "create"):
        original_create = completions.create

        @functools.wraps(original_create)
        def create(*args, **kwargs):
            return _flatten_reasoning_content(original_create(*args, **kwargs))

        try:
            completions.create = create
        except AttributeError:
            object.__setattr__(completions, "create", create)
    return client


def _create_mistral_client(async_mode: bool, instructor_mode) -> Union[Instructor, AsyncInstructor]:
    """Crée un client Mistral."""
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
    if not MISTRAL_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="La clé API Mistral n'est pas définie. Veuillez configurer la variable d'environnement MISTRAL_API_KEY."
        )

    mistral_client = _patch_mistral_completions(Mistral(api_key=MISTRAL_API_KEY), async_mode)

    client = instructor.from_mistral(
        mistral_client,
        use_async=async_mode,
        mode=instructor_mode,
    )

    return client

def _create_ollama_client(async_mode: bool, extra_body: dict = {}, instructor_mode: instructor.Mode = instructor.Mode.TOOLS) -> Union[Instructor, AsyncInstructor]:
    """Crée un client Ollama."""

    client = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
        ) if not async_mode else AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    # extra_body permet d'indiquer le niveau de raisonnement sur les modèles concernés
    # comme les modèles Qwen
    # https://huggingface.co/Qwen/Qwen3.5-0.8B
    print(extra_body)
    instructor_instance = instructor.from_openai(client, extra_body=extra_body, mode=instructor_mode)
    return instructor_instance
