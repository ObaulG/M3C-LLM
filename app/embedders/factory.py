"""Factory pour créer et gérer les embedders.

Ce module fournit des fonctions pour instancier des embedders à partir
de configurations et pour lister les embedders disponibles.
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml

from .BaseEmbedder import BaseEmbedder
from .api.MistralEmbedder import MistralEmbedder
from .local.DockerEmbedder import DockerEmbedder

configs = []

def _get_configs_dir() -> Path:
    """Retourne le chemin du répertoire des configurations d'embedders."""
    # Chemin relatif depuis ce fichier
    return Path(__file__).parent.parent.parent / "config" / "embedders"


def get_embedder_configs() -> List[Dict[str, Any]]:
    """Charge et retourne toutes les configurations d'embedders depuis config/embedders/.
    
    Returns:
        Liste de dictionnaires contenant les configurations de chaque embedder.
    """
    configs = []
    configs_dir = _get_configs_dir()
    
    if not configs_dir.exists():
        return configs
    
    for config_file in sorted(configs_dir.glob("*.yaml")):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if config and isinstance(config, dict):
                    config['_file'] = config_file.name
                    config['_path'] = str(config_file)
                    configs.append(config)
        except (yaml.YAMLError, OSError) as e:
            print(f"Erreur lors du chargement de {config_file}: {e}")
    
    return configs


def create_mistral_embedder(api_key: Optional[str] = None, model: str = "mistral-embed", dimension: int = 1024) -> MistralEmbedder:
    """Crée un embedder pour l'API Mistral.
    
    Args:
        api_key: Clé API Mistral. Si None, utilise MISTRAL_API_KEY depuis les variables d'environnement.
        model: Nom du modèle d'embedding (par défaut: "mistral-embed").
        dimension: Dimension des embeddings (par défaut: 1024).
    
    Returns:
        Une instance de MistralEmbedder.
    
    Raises:
        ValueError: Si aucune clé API n'est disponible.
    """
    actual_api_key = api_key or os.getenv("MISTRAL_API_KEY")
    if not actual_api_key:
        raise ValueError("Aucune clé API Mistral fournie et MISTRAL_API_KEY non trouvée dans les variables d'environnement")
    
    return MistralEmbedder(api_key=actual_api_key, model=model, dimension=dimension)


def create_docker_embedder(config: Dict[str, Any]) -> DockerEmbedder:
    """Crée un embedder pour un modèle local via Docker.
    
    Args:
        config: Dictionnaire de configuration contenant:
            - name: Nom de l'embedder
            - model_name: Nom du modèle
            - dimension: Dimension des embeddings
            - docker: Configuration Docker (image, port, gpu, etc.)
            - api: Configuration de l'API (endpoint, batch_size, etc.)
    
    Returns:
        Une instance de DockerEmbedder.
    """
    docker_config = config.get("docker", {})
    api_config = config.get("api", {})
    
    return DockerEmbedder(
        model_name=config.get("model_name", config.get("name", "unknown")),
        api_endpoint=api_config.get("endpoint", "http://localhost:8000"),
        docker_config=docker_config,
        dimension=config.get("dimension", 1024),
        batch_size=api_config.get("batch_size", 32),
        timeout=api_config.get("timeout", 30),
    )


def create_embedder(config_name: str) -> BaseEmbedder:
    """Crée un embedder à partir d'une configuration nommée.
    
    Args:
        config_name: Nom du fichier de configuration (sans extension .yaml).
    
    Returns:
        Une instance de BaseEmbedder (MistralEmbedder ou DockerEmbedder).
    
    Raises:
        FileNotFoundError: Si la configuration n'existe pas.
        ValueError: Si la configuration est invalide ou si le type n'est pas supporté.
    """
    configs_dir = _get_configs_dir()
    config_file = configs_dir / f"{config_name}.yaml"

    if not config_file.exists():
        raise FileNotFoundError(f"Configuration '{config_name}' introuvable dans {configs_dir}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if not config:
        raise ValueError(f"Configuration '{config_name}' est vide")

    embedder_type = config.get("type", "api")
    
    if embedder_type == "api" or "mistral" in config.get("name", "").lower():
        return create_mistral_embedder(
            model=config.get("model_name", "mistral-embed"),
            dimension=config.get("dimension", 1024)
        )
    elif embedder_type == "docker" or "docker" in config.get("name", "").lower():
        return create_docker_embedder(config)
    else:
        # Par défaut, essayer de déterminer le type
        if "api" in config:
            return create_mistral_embedder(
                model=config.get("model_name", "mistral-embed"),
                dimension=config.get("dimension", 1024)
            )
        elif "docker" in config:
            return create_docker_embedder(config)
        else:
            raise ValueError(f"Type d'embedder non supporté dans la configuration '{config_name}'")


def get_default_embedder() -> BaseEmbedder:
    """Crée et retourne l'embedder par défaut.
    
    L'embedder par défaut est MistralEmbedder utilisant MISTRAL_API_KEY.
    
    Returns:
        Une instance de BaseEmbedder.
    
    Raises:
        ValueError: Si aucun embedder par défaut ne peut être créé.
    """
    # Essayer de créer un MistralEmbedder avec la clé API
    try:
        return create_mistral_embedder()
    except ValueError:
        pass
    
    # Sinon, essayer le premier embedder configuré dans config/embedders/
    configs = get_embedder_configs()
    if configs:
        # Prendre la première configuration et essayer de créer l'embedder
        first_config = configs[0]
        try:
            if "docker" in first_config:
                return create_docker_embedder(first_config)
            else:
                return create_mistral_embedder(
                    model=first_config.get("model_name", "mistral-embed"),
                    dimension=first_config.get("dimension", 1024)
                )
        except Exception:
            pass
    
    raise ValueError("Impossible de créer un embedder par défaut. Vérifiez que MISTRAL_API_KEY est définie ou qu'une configuration d'embedder existe.")


def list_available_embedders() -> List[Dict[str, Any]]:
    """Retourne la liste des embedders disponibles avec leurs informations.
    
    Cette fonction est utilisée par l'API pour lister les embedders configurés.
    
    Returns:
        Liste de dictionnaires contenant:
        - name: Nom de l'embedder
        - type: Type (api ou docker)
        - model_name: Nom du modèle
        - dimension: Dimension des embeddings
        - is_default: Si c'est l'embedder par défaut
        - available: Si l'embedder peut être instancié
    """
    result = []
    
    # Ajouter l'embedder Mistral (API) s'il est configuré
    if os.getenv("MISTRAL_API_KEY"):
        result.append({
            "name": "mistral-embed",
            "type": "api",
            "model_name": "mistral-embed",
            "dimension": 1024,
            "is_default": True,
            "available": True,
            "description": "Embedder via l'API Mistral"
        })
    
    # Ajouter les embedders configurés dans config/embedders/
    configs = get_embedder_configs()
    for i, config in enumerate(configs):
        embedder_info = {
            "name": config.get("name", config.get("model_name", f"config_{i}")),
            "type": "docker" if "docker" in config else "api",
            "model_name": config.get("model_name", "unknown"),
            "dimension": config.get("dimension", 1024),
            "is_default": False,
            "available": True,
            "description": config.get("description", ""),
            "config_file": config.get("_file", ""),
        }
        result.append(embedder_info)
    
    return result
