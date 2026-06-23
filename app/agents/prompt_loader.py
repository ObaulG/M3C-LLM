"""
Prompt Loader Module

Charge les SystemPromptGenerator depuis des fichiers YAML.
Supporte les templates Jinja2 pour les paramètres dynamiques.
Garde les anciennes définitions comme fallback.
"""

from pathlib import Path
import yaml
from jinja2 import Template
from atomic_agents.context import SystemPromptGenerator
from typing import Dict, Any, Optional

PROMPTS_DIR = Path(__file__).parent / "prompts"

# Cache des prompts chargés
_prompts_cache: Dict[str, Dict[str, SystemPromptGenerator]] = {}


def load_prompt_file(filename: str) -> Dict[str, SystemPromptGenerator]:
    """
    Charge un fichier YAML de prompts et retourne un dict {nom: SystemPromptGenerator}.
    
    Args:
        filename: Nom du fichier YAML (sans extension)
        
    Returns:
        Dictionnaire mapping nom_prompt -> SystemPromptGenerator
    """
    if filename in _prompts_cache:
        return _prompts_cache[filename]
    
    filepath = PROMPTS_DIR / f"{filename}.yaml"
    
    if not filepath.exists():
        raise FileNotFoundError(f"Prompt file '{filename}.yaml' not found in {PROMPTS_DIR}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    if data is None:
        data = {}
    
    result = {}
    for name, config in data.items():
        result[name] = _create_prompt_generator(config)
    
    _prompts_cache[filename] = result
    return result


def _create_prompt_generator(config: Dict[str, list]) -> SystemPromptGenerator:
    """
    Crée un SystemPromptGenerator à partir d'une config dict.
    
    Args:
        config: Dictionnaire avec keys 'background', 'steps', 'output_instructions'
        
    Returns:
        SystemPromptGenerator
    """
    return SystemPromptGenerator(
        background=config.get('background', []),
        steps=config.get('steps', []),
        output_instructions=config.get('output_instructions', [])
    )


def get_prompt(filename: str, prompt_name: str, **kwargs) -> SystemPromptGenerator:
    """
    Récupère un prompt spécifique avec rendu de template.
    
    Args:
        filename: Nom du fichier YAML (sans extension)
        prompt_name: Nom du prompt dans le fichier
        **kwargs: Variables pour le rendu de template (ex: max_words=100)
        
    Returns:
        SystemPromptGenerator avec les valeurs rendues
    """
    try:
        prompts = load_prompt_file(filename)
        
        if prompt_name not in prompts:
            raise ValueError(f"Prompt '{prompt_name}' not found in {filename}.yaml")
        
        # Si des kwargs sont fournis, on doit recréer le prompt avec rendu
        if kwargs:
            config = prompts[prompt_name]
            rendered_config = {
                'background': [Template(t).render(**kwargs) for t in config.background],
                'steps': [Template(t).render(**kwargs) for t in config.steps],
                'output_instructions': [Template(t).render(**kwargs) for t in config.output_instructions],
            }
            return _create_prompt_generator(rendered_config)
        
        return prompts[prompt_name]
    except Exception:
        # Fallback: retourner None pour permettre l'utilisation des anciennes définitions
        return None


def clear_cache():
    """Efface le cache des prompts (utile pour le hot-reload en dev)"""
    _prompts_cache.clear()
