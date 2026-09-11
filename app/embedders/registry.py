"""Registre global des embedders disponibles.

Ce module fournit un dictionnaire centralisé qui mappe les noms des embedders
vers leurs propriétés, ainsi que des fonctions pour créer des instances.
"""

import os
from typing import Dict, Any, Optional

from .BaseEmbedder import BaseEmbedder

# Dictionnaire global qui mappe nom -> propriétés
# Initialisé par _init_embedders() au premier import
EMBEDDERS: Dict[str, Dict[str, Any]] = {}


def register_embedder(name: str, properties: Dict[str, Any]) -> None:
    """Enregistre un embedder dans le registre.
    
    Args:
        name: Nom unique de l'embedder
        properties: Dictionnaire des propriétés (type, model_name, dimension, etc.)
    """
    EMBEDDERS[name] = properties


def get_embedders() -> Dict[str, Dict[str, Any]]:
    """Retourne le dictionnaire complet des embedders."""
    return EMBEDDERS


def get_embedder_list() -> list:
    """Retourne la liste des propriétés des embedders."""
    return list(EMBEDDERS.values())


def get_embedder_names() -> list:
    """Retourne la liste des noms des embedders."""
    return list(EMBEDDERS.keys())


def get_default_embedder_name() -> Optional[str]:
    """Retourne le nom de l'embedder par défaut."""
    for name, props in EMBEDDERS.items():
        if props.get("is_default", False):
            return name
    return list(EMBEDDERS.keys())[0] if EMBEDDERS else None


def get_embedder_instance(name: str) -> BaseEmbedder:
    """Crée une instance d'embedder à partir de son nom.
    
    Args:
        name: Nom de l'embedder dans le registre
        
    Returns:
        Une instance de BaseEmbedder
        
    Raises:
        ValueError: Si l'embedder n'est pas trouvé ou si le type est inconnu
    """
    if name not in EMBEDDERS:
        raise ValueError(f"Embedder '{name}' non trouvé dans le registre. Embedders disponibles: {get_embedder_names()}")
    
    props = EMBEDDERS[name]
    embedder_type = props.get("type", "api")
    
    if embedder_type == "api" or name.startswith("mistral-"):
        from .api.MistralEmbedder import MistralEmbedder
        return MistralEmbedder(
            #api_key=os.getenv("MISTRAL_API_KEY", ""),
            api_key="FnazLcbitTHAN4jSQt82sXusu2svW0hC",
            model=props.get("model", props.get("model_name", name)),
            dimension=props.get("dimension", 1024)
        )
    elif embedder_type == "docker":
        from .local.DockerEmbedder import DockerEmbedder
        return DockerEmbedder(
            model_name=props.get("model_name", name),
            api_endpoint=props.get("endpoint", props.get("api_endpoint", "http://localhost:8000")),
            docker_config=props.get("docker", {}),
            dimension=props.get("dimension", 1024),
            batch_size=props.get("batch_size", 32),
            timeout=props.get("timeout", 30)
        )
    else:
        raise ValueError(f"Type d'embedder inconnu: {embedder_type}")


def get_default_embedder() -> Optional[BaseEmbedder]:
    """Retourne une instance de l'embedder par défaut."""
    default_name = get_default_embedder_name()
    if default_name:
        return get_embedder_instance(default_name)
    return None
