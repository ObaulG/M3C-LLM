"""Router FastAPI pour la liste des modèles LLM disponibles.

Expose la route GET /api/models qui retourne l'ensemble des modèles et de
leurs fournisseurs (Mistral, Google, Ollama, etc.) définis dans
config/models/models.csv. Ce fichier CSV est la source unique destinée à
alimenter toutes les pages HTML proposant la sélection d'un modèle.
"""

import csv
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/models", tags=["Models"])

MODELS_CSV_PATH = Path(__file__).parent.parent.parent / "config" / "models" / "models.csv"

PROVIDER_LABELS = {
    "mistral": "Mistral",
    "google": "Gemini",
    "ollama": "Local",
}

# Ordre d'affichage des fournisseurs dans les listes déroulantes
PROVIDER_ORDER = ["ollama", "mistral", "google"]


class ModelInfo(BaseModel):
    """Informations sur un modèle LLM disponible"""
    model: str = Field(..., description="Identifiant technique du modèle")
    provider: str = Field(..., description="Fournisseur du modèle (mistral, google, ollama)")
    label: str = Field(..., description="Libellé lisible du modèle")


class ModelsListResponse(BaseModel):
    """Réponse de la route GET /api/models"""
    models: List[ModelInfo] = Field(..., description="Liste des modèles disponibles")
    providers: List[str] = Field(..., description="Fournisseurs distincts, dans l'ordre d'affichage")


def load_models_from_csv() -> List[Dict[str, str]]:
    """Charge les modèles depuis config/models/models.csv.

    Returns:
        Liste de dictionnaires avec les clés model, provider et label.

    Raises:
        HTTPException: Si le fichier CSV est introuvable ou illisible.
    """
    if not MODELS_CSV_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Fichier de configuration des modèles introuvable: {MODELS_CSV_PATH}",
        )

    models = []
    try:
        with open(MODELS_CSV_PATH, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                model = (row.get("model") or "").strip()
                provider = (row.get("provider") or "").strip()
                label = (row.get("label") or "").strip() or model
                if model and provider:
                    models.append({
                        "model": model,
                        "provider": provider,
                        "label": label,
                    })
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la lecture du fichier de modèles: {e}",
        )

    if not models:
        raise HTTPException(
            status_code=500,
            detail="Le fichier de configuration des modèles est vide",
        )

    return models


@router.get("", response_model=ModelsListResponse)
def get_models() -> ModelsListResponse:
    """Retourne la liste des modèles LLM et de leurs fournisseurs."""
    models = load_models_from_csv()

    providers = [p for p in PROVIDER_ORDER if any(m["provider"] == p for m in models)]
    providers += [m["provider"] for m in models if m["provider"] not in providers]

    return ModelsListResponse(
        models=[ModelInfo(**m) for m in models],
        providers=providers,
    )
