import os
from typing import Union, Literal, Optional
import instructor
from instructor import Instructor, AsyncInstructor
from mistralai.client import Mistral
from fastapi import HTTPException
from openai import OpenAI, AsyncOpenAI


GOOGLE_MODELS = ["gemma-3-4b-it", "gemma-3-12b-it", "gemma-3-27b-it"]

def create_client(
    provider: Literal["mistral", "ollama", "google"],
    model: Optional[str],
    async_mode: bool = False,
) -> Union[Instructor, AsyncInstructor]:
    """
    Crée et retourne un client configuré avec Instructor.

    Args:
        provider: Le fournisseur de modèle ("mistral" ou "ollama").
        model: Le nom du modèle (obligatoire pour google).
        async_mode: Si True, retourne un client asynchrone.

    Returns:
        Une instance de Instructor ou AsyncInstructor.

    Raises:
        HTTPException: Si la configuration est invalide.
    """
    if provider == "mistral":
        return _create_mistral_client(async_mode)
    elif provider == "ollama":
        return _create_ollama_client(async_mode)
    elif provider == "google":
        return _create_gemma_client(model, async_mode)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Fournisseur inconnu: {provider}. Utilisez 'mistral' ou 'ollama'."
        )

def _create_gemma_client(model: str, async_mode: bool) -> Union[Instructor, AsyncInstructor]:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="La clé API Mistral n'est pas définie. Veuillez configurer la variable d'environnement MISTRAL_API_KEY."
        )

    client = instructor.from_provider(f"google/{model}", async_client=async_mode)
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
        use_async=async_mode
    )

    return client

def _create_ollama_client(async_mode: bool) -> Union[Instructor, AsyncInstructor]:
    """Crée un client Ollama."""
    client = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
        ) if not async_mode else AsyncOpenAI(base_url="http://localhost:11434/v1",
            api_key="ollama",
    )
    instructor_instance = instructor.from_openai(client)
    return instructor_instance
