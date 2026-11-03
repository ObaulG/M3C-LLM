"""Calcul du coût des requêtes LLM (en euros).

La grille tarifaire est déclarée dans config/models/models.csv, colonnes
price_input_eur, price_cached_input_eur et price_output_eur (euros par
million de tokens). Les prix Mistral proviennent de la grille officielle
(docs.mistral.ai, tarifs USD constatés) convertis en euros au taux 0.85
EUR/USD constaté sur la page officielle de tarification ; ils sont à
mettre à jour manuellement en cas de changement.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

MODELS_CSV_PATH = Path(__file__).parent.parent / "config" / "models" / "models.csv"


@lru_cache(maxsize=1)
def load_prices() -> Dict[str, Dict[str, Optional[float]]]:
    """Charge les prix par million de tokens depuis config/models/models.csv.

    Returns:
        Dictionnaire {model: {"input": x, "cached_input": y, "output": z}}.
        Les valeurs manquantes valent None (modèle non tarifé).
    """
    prices: Dict[str, Dict[str, Optional[float]]] = {}
    try:
        import csv

        with open(MODELS_CSV_PATH, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                model = (row.get("model") or "").strip()
                if not model:
                    continue
                prices[model] = {
                    "input": _parse_price(row.get("price_input_eur")),
                    "cached_input": _parse_price(row.get("price_cached_input_eur")),
                    "output": _parse_price(row.get("price_output_eur")),
                }
    except OSError as e:
        logger.warning(f"Impossible de charger la grille tarifaire ({MODELS_CSV_PATH}): {e}")
    return prices


def _parse_price(value) -> Optional[float]:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def compute_cost_eur(model: str,
                     input_tokens: int,
                     cached_tokens: int = 0,
                     output_tokens: int = 0) -> Optional[Dict[str, float]]:
    """Calcule le coût détaillé d'une requête en euros.

    Les tokens d'entrée servis depuis le cache de prompt sont facturés au
    tarif "cached input" (10 % du tarif input chez Mistral), les tokens
    d'entrée restants au tarif input, et les tokens de sortie au tarif
    output.

    Args:
        model: Identifiant technique du modèle (ex. "mistral-small-2603").
        input_tokens: Nombre total de tokens d'entrée (cache inclus).
        cached_tokens: Nombre de tokens d'entrée servis depuis le cache.
        output_tokens: Nombre de tokens de sortie.

    Returns:
        Dictionnaire {"input_eur", "cached_input_eur", "output_eur", "total_eur"},
        ou None si le modèle n'est pas présent dans la grille tarifaire.
    """
    prices = load_prices().get(model)
    if not prices or prices["input"] is None or prices["output"] is None:
        return None

    cached_tokens = max(0, min(int(cached_tokens or 0), int(input_tokens or 0)))
    fresh_tokens = int(input_tokens or 0) - cached_tokens

    cached_price = prices["cached_input"]
    if cached_price is None:
        cached_price = prices["input"]

    input_eur = fresh_tokens * prices["input"] / 1_000_000
    cached_eur = cached_tokens * cached_price / 1_000_000
    output_eur = int(output_tokens or 0) * prices["output"] / 1_000_000

    return {
        "input_eur": round(input_eur, 8),
        "cached_input_eur": round(cached_eur, 8),
        "output_eur": round(output_eur, 8),
        "total_eur": round(input_eur + cached_eur + output_eur, 8),
    }


def usage_from_langchain_message(message) -> Optional[Dict[str, int]]:
    """Extrait la consommation réelle d'un message LangChain (AIMessage).

    Le cache de prompt est exposé par les intégrations LangChain récentes via
    input_token_details.cached_tokens (usage_metadata) ou
    prompt_tokens_details.cached_tokens (response_metadata.token_usage).

    Args:
        message: Message LangChain (BaseMessage / AIMessage).

    Returns:
        Dictionnaire {"input_tokens", "cached_tokens", "output_tokens"},
        ou None si aucune information d'usage n'est disponible.
    """
    usage_meta = getattr(message, "usage_metadata", None) or {}
    response_meta = getattr(message, "response_metadata", None) or {}
    token_usage = response_meta.get("token_usage") if isinstance(response_meta, dict) else None

    input_tokens = usage_meta.get("input_tokens")
    output_tokens = usage_meta.get("output_tokens")
    if input_tokens is None and token_usage:
        input_tokens = token_usage.get("prompt_tokens")
        output_tokens = token_usage.get("completion_tokens", output_tokens)
    if input_tokens is None:
        return None

    cached_tokens = 0
    input_details = usage_meta.get("input_token_details") or {}
    if isinstance(input_details, dict):
        cached_tokens = input_details.get("cached_tokens") or 0
    if not cached_tokens and token_usage:
        prompt_details = token_usage.get("prompt_tokens_details") or {}
        if isinstance(prompt_details, dict):
            cached_tokens = prompt_details.get("cached_tokens") or 0

    return {
        "input_tokens": int(input_tokens),
        "cached_tokens": int(cached_tokens),
        "output_tokens": int(output_tokens or 0),
    }


def usage_from_mistral_completion(completion) -> Optional[Dict[str, int]]:
    """Extrait la consommation réelle d'une completion du client Mistral.

    Les completions de l'API Mistral exposent usage.prompt_tokens,
    usage.completion_tokens et usage.prompt_tokens_details.cached_tokens.

    Args:
        completion: Completion renvoyée par le SDK mistralai.

    Returns:
        Dictionnaire {"input_tokens", "cached_tokens", "output_tokens"},
        ou None si la completion ne contient pas d'usage.
    """
    usage = getattr(completion, "usage", None)
    if usage is None:
        return None

    prompt_tokens = getattr(usage, "prompt_tokens", None)
    if prompt_tokens is None:
        return None

    cached_tokens = 0
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        cached_tokens = getattr(details, "cached_tokens", None) or 0

    return {
        "input_tokens": int(prompt_tokens),
        "cached_tokens": int(cached_tokens),
        "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
    }
