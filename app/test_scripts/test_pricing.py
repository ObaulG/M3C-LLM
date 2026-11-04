# test_pricing.py
"""
Tests du module app/pricing.py : calcul du coût des requêtes LLM en euros
\u00e0 partir de la grille tarifaire de config/models/models.csv.

Ex\u00e9cution : python3 app/test_scripts/test_pricing.py (depuis la racine du repo)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pricing import (  # noqa: E402
    compute_cost_eur,
    load_prices,
    usage_from_langchain_message,
    usage_from_mistral_completion,
)


def test_load_prices():
    prices = load_prices()
    assert "mistral-small-2603" in prices, "mistral-small-2603 doit \u00eatre tarif\u00e9"
    assert "ministral-3b-2512" in prices
    assert prices["mistral-large-4"]["input"] == 0.595
    assert prices["mistral-large-4"]["cached_input"] == 0.0595
    assert prices["mistral-large-4"]["output"] == 1.785
    # les mod\u00e8les non tarif\u00e9s (ollama, google) n'ont pas de prix
    assert prices.get("llama3.2:1b", {}).get("input") is None
    print("test_load_prices OK")


def test_compute_cost_without_cache():
    cost = compute_cost_eur("mistral-small-2603", input_tokens=1000, cached_tokens=0, output_tokens=500)
    assert cost is not None
    expected = 1000 * 0.1275 / 1_000_000 + 500 * 0.51 / 1_000_000
    assert abs(cost["total_eur"] - expected) < 1e-9
    assert cost["cached_input_eur"] == 0.0
    print("test_compute_cost_without_cache OK")


def test_compute_cost_with_partial_cache():
    cost = compute_cost_eur("mistral-large-4", input_tokens=1000, cached_tokens=400, output_tokens=100)
    assert cost is not None
    expected = (600 * 0.595 + 400 * 0.0595 + 100 * 1.785) / 1_000_000
    assert abs(cost["total_eur"] - expected) < 1e-9
    print("test_compute_cost_with_partial_cache OK")


def test_compute_cost_unknown_model():
    assert compute_cost_eur("modele-inconnu", 100, 0, 100) is None
    assert compute_cost_eur("llama3.2:1b", 100, 0, 100) is None
    print("test_compute_cost_unknown_model OK")


def test_compute_cost_defensive_inputs():
    cost = compute_cost_eur("ministral-3b-2512", input_tokens=None, cached_tokens=-5, output_tokens="100")
    assert cost is not None
    assert cost["total_eur"] == 100 * 0.085 / 1_000_000
    print("test_compute_cost_defensive_inputs OK")


def test_usage_from_langchain_message():
    class Msg:
        usage_metadata = {"input_tokens": 944, "output_tokens": 686, "total_tokens": 1630,
                          "input_token_details": {"cached_tokens": 100}}
        response_metadata = {"token_usage": {"prompt_tokens": 944, "completion_tokens": 686,
                                             "prompt_tokens_details": {"cached_tokens": 100}}}

    usage = usage_from_langchain_message(Msg())
    assert usage == {"input_tokens": 944, "cached_tokens": 100, "output_tokens": 686}

    class MsgNoDetails:
        usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        response_metadata = {}

    usage = usage_from_langchain_message(MsgNoDetails())
    assert usage == {"input_tokens": 10, "cached_tokens": 0, "output_tokens": 5}

    class Empty:
        usage_metadata = None
        response_metadata = None

    assert usage_from_langchain_message(Empty()) is None
    print("test_usage_from_langchain_message OK")


def test_usage_from_mistral_completion():
    class Details:
        cached_tokens = 42

    class Usage:
        prompt_tokens = 1013
        completion_tokens = 30
        prompt_tokens_details = Details()

    class Completion:
        usage = Usage()

    usage = usage_from_mistral_completion(Completion())
    assert usage == {"input_tokens": 1013, "cached_tokens": 42, "output_tokens": 30}

    class NoUsage:
        usage = None

    assert usage_from_mistral_completion(NoUsage()) is None
    print("test_usage_from_mistral_completion OK")


if __name__ == "__main__":
    test_load_prices()
    test_compute_cost_without_cache()
    test_compute_cost_with_partial_cache()
    test_compute_cost_unknown_model()
    test_compute_cost_defensive_inputs()
    test_usage_from_langchain_message()
    test_usage_from_mistral_completion()
    print("\nTous les tests pricing passent.")
