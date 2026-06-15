"""Module des embedders pour le système RAG.

Ce module fournit une architecture unifiée pour gérer différents types d'embedders:
- API distantes (Mistral, etc.)
- Modèles locaux (via Docker)

Le registre des embedders est initialisé automatiquement au premier import.

Exemple d'utilisation:
    from app.embedders import EMBEDDERS, get_embedder_instance, get_embedder_list
    
    # Lister les embedders disponibles
    available = get_embedder_list()
    
    # Obtenir une instance
    embedder = get_embedder_instance("mistral-embed")
    
    # Accéder au dictionnaire global
    from app.embedders.registry import EMBEDDERS
"""

import os
from pathlib import Path
import yaml

from .BaseEmbedder import BaseEmbedder
from .api.MistralEmbedder import MistralEmbedder
from .local.DockerEmbedder import DockerEmbedder
from .registry import (
    EMBEDDERS,
    register_embedder,
    get_embedders,
    get_embedder_list,
    get_embedder_names,
    get_default_embedder_name,
    get_embedder_instance,
    get_default_embedder,
)


def _init_embedders():
    """Initialise le registre des embedders.
    
    Cette fonction est appelée automatiquement au premier import du module.
    Elle enregistre:
    - L'embedder Mistral (API) si MISTRAL_API_KEY est défini
    - Les embedders configurés dans config/embedders/*.yaml
    """
    # Embedder Mistral par défaut
    if os.getenv("MISTRAL_API_KEY"):
        register_embedder("mistral-embed", {
            "type": "api",
            "name": "mistral-embed",
            "model_name": "mistral-embed",
            "dimension": 1024,
            "is_default": True,
            "description": "Embedder via l'API Mistral"
        })
    
    # Charger les configs depuis config/embedders/
    configs_dir = Path(__file__).parent.parent.parent / "config" / "embedders"
    if configs_dir.exists():
        for config_file in sorted(configs_dir.glob("*.yaml")):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config and isinstance(config, dict):
                        # Utiliser name ou model_name comme clé
                        name = config.get("name", config.get("model_name", config_file.stem))
                        # Définir le type par défaut
                        if "type" not in config:
                            config["type"] = "docker"
                        if "is_default" not in config:
                            config["is_default"] = False
                        register_embedder(name, config)
            except (yaml.YAMLError, OSError) as e:
                print(f"Avertissement: Impossible de charger {config_file}: {e}")

    print("Embedders disponibles:")
    for embedder in EMBEDDERS.values():
        print(embedder)

# Initialiser au premier import
_init_embedders()


# Garder la compatibilité ascendante avec l'ancienne API
from .factory import (
    create_embedder,
    create_mistral_embedder,
    create_docker_embedder,
    list_available_embedders as list_available_embedders_deprecated,
    get_default_embedder as get_default_embedder_deprecated,
    get_embedder_configs,
)

__all__ = [
    # Registre
    "EMBEDDERS",
    "register_embedder",
    "get_embedders",
    "get_embedder_list",
    "get_embedder_names",
    "get_default_embedder_name",
    "get_embedder_instance",
    "get_default_embedder",
    # Classes
    "BaseEmbedder",
    "MistralEmbedder",
    "DockerEmbedder",
    # Factory (compatibilité)
    "create_embedder",
    "create_mistral_embedder",
    "create_docker_embedder",
    "get_embedder_configs",
]
