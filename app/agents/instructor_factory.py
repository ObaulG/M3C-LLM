import os
from typing import Union, Literal, Optional
import instructor
from instructor import Instructor, AsyncInstructor
from mistralai.client import Mistral
from fastapi import HTTPException
from openai import OpenAI, AsyncOpenAI
from google import genai
from google.genai import types

MISTRAL_MODELS = [
    "ministral-3b-2410", "ministral-8b-2410", "open-mistral-7b", "open-mistral-nemo",
    "mistral-tiny", "mistral-small", "mistral-medium", "mistral-large-2411"
]
GOOGLE_MODELS = ["gemma-4-26b-a4b-it", "gemma-4-31b-it"]
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
        return _create_mistral_client(async_mode)
    elif provider == "ollama":
        return _create_ollama_client(async_mode, extra_body, instructor_mode)
    elif provider == "google":
        return _create_gemma_client(model, async_mode)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Fournisseur inconnu: {provider}. Utilisez 'mistral' ou 'ollama'."
        )

def _create_gemma_client(model: str, async_mode: bool) -> Union[Instructor, AsyncInstructor]:
    GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GOOGLE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="La clé API Google n'est pas définie. Veuillez configurer la variable d'environnement GEMINI_API_KEY."
        )

    client = instructor.from_provider(f"google/{model}",
                                      api_key=GOOGLE_API_KEY,
                                      async_client=async_mode)
   #                                   mode=instructor.Mode.GENAI_TOOLS)

    return client
def _create_mistral_client(async_mode: bool) -> Union[Instructor, AsyncInstructor]:
    """Crée un client Mistral."""
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
    if not MISTRAL_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="La clé API Mistral n'est pas définie. Veuillez configurer la variable d'environnement MISTRAL_API_KEY."
        )

    client = instructor.from_mistral(
        Mistral(api_key=MISTRAL_API_KEY),
        use_async=async_mode,
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
