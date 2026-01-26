# dependencies.py
import os
import instructor
import mistralai
from fastapi import Depends, HTTPException

def get_mistral_client() -> mistralai.Mistral:
    """
    Crée et retourne un client Mistral configuré avec Instructor.
    Lève une exception si la clé API n'est pas définie.
    """
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
    if not MISTRAL_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="La clé API Mistral n'est pas définie. Veuillez configurer la variable d'environnement MISTRAL_API_KEY."
        )

    # Initialiser le client Mistral avec Instructor
    client = instructor.from_mistral(mistralai.Mistral(api_key=MISTRAL_API_KEY))
    return client
