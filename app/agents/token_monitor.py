# agents/token_monitor.py
"""
Utilitaire pour surveiller et afficher le nombre de tokens en entrée et en sortie
lors des appels aux agents AtomicAgent.

Cet utilitaire peut être utilisé pour envelopper les appels aux agents et fournir
des informations détaillées sur l'utilisation des tokens.
"""

from dataclasses import dataclass, field
from typing import TypeVar, Any, Callable, Optional, Tuple, Dict
from atomic_agents import AtomicAgent, BaseIOSchema
from atomic_agents.utils.token_counter import get_token_counter, TokenCountResult
import logging
from functools import wraps

try:
    from app.pricing import compute_cost_eur, usage_from_mistral_completion
except ImportError:
    from pricing import compute_cost_eur, usage_from_mistral_completion

# Type variables pour les schémas d'entrée/sortie
InputSchema = TypeVar('InputSchema', bound=BaseIOSchema)
OutputSchema = TypeVar('OutputSchema', bound=BaseIOSchema)

logger = logging.getLogger(__name__)


@dataclass
class TokenUsageInfo:
    """
    Consommation d'un appel à un agent AtomicAgent, avec le coût estimé
    de la requête en euros lorsque le modèle est présent dans la grille
    tarifaire (config/models/models.csv).

    Attributes:
        input_tokens: Nombre total de tokens d'entrée (cache inclus)
        output_tokens: Nombre de tokens de sortie
        cached_tokens: Nombre de tokens d'entrée servis depuis le cache de prompt
        model: Identifiant du modèle utilisé
        usage_source: "api" si la consommation provient de la réponse du
            fournisseur (client Mistral), "estimated" si elle est estimée localement
        cost_eur: Coût total estimé de la requête en euros (None si le
            modèle n'est pas tarifé)
        cost_detail: Détail du coût (input, cache, output) en euros
    """
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    model: str = ""
    usage_source: str = "estimated"
    cost_eur: Optional[float] = None
    cost_detail: Optional[Dict[str, float]] = field(default=None)

    def to_metadata(self) -> Dict[str, Any]:
        """Représentation sous forme de métadonnées de réponse."""
        metadata: Dict[str, Any] = {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_tokens": self.cached_tokens,
            "usage_source": self.usage_source,
        }
        if self.cost_eur is not None:
            metadata["cost_eur"] = self.cost_eur
            metadata["cost_detail"] = self.cost_detail
        return metadata


def _last_completion_of(agent) -> Any:
    """
    Récupère la dernière completion brute renvoyée par le client
    sous-jacent de l'agent (client Instructor), si disponible.
    """
    client = getattr(agent, "client", None)
    if client is None:
        return None
    for attr in ("last_completion", "_last_completion"):
        completion = getattr(client, attr, None)
        if completion is not None:
            return completion
    return None


def _usage_info_for(agent, estimated_input_tokens: int, output_tokens: int) -> TokenUsageInfo:
    """
    Construit les informations de consommation d'un appel d'agent. Tente
    d'abord de lire la consommation réelle fournie par le fournisseur
    (usage de la dernière completion du client Mistral, incluant les
    tokens en cache), puis retombe sur le comptage local estimé. Calcule
    ensuite le coût estimé en euros à partir du modèle.
    """
    model = getattr(agent, "model", "") or ""
    usage_info = TokenUsageInfo(
        input_tokens=estimated_input_tokens,
        output_tokens=output_tokens,
        model=model,
        usage_source="estimated",
    )

    completion = _last_completion_of(agent)
    if completion is not None:
        usage = usage_from_mistral_completion(completion)
        if usage is not None:
            usage_info.input_tokens = usage["input_tokens"]
            usage_info.cached_tokens = usage["cached_tokens"]
            usage_info.output_tokens = usage["output_tokens"]
            usage_info.usage_source = "api"

    cost_detail = compute_cost_eur(
        model,
        input_tokens=usage_info.input_tokens,
        cached_tokens=usage_info.cached_tokens,
        output_tokens=usage_info.output_tokens,
    )
    if cost_detail is not None:
        usage_info.cost_eur = cost_detail["total_eur"]
        usage_info.cost_detail = cost_detail

    return usage_info


def _count_user_input_tokens(agent: AtomicAgent[InputSchema, OutputSchema], 
                             user_input: Optional[InputSchema]) -> int:
    """
    Compte les tokens du user_input.
    
    Args:
        agent: L'agent AtomicAgent
        user_input: L'entrée utilisateur à compter
        
    Returns:
        Le nombre de tokens dans le user_input (0 si None)
    """
    if user_input is None:
        return 0
    
    try:
        counter = get_token_counter()
        
        # Convertir user_input en texte (comme dans _count_output_tokens)
        if hasattr(user_input, 'model_dump'):
            user_input_text = str(user_input.model_dump())
        else:
            user_input_text = str(user_input)
            
        return counter.count_text(agent.model, user_input_text)
        
    except Exception as e:
        logger.warning(f"Impossible de compter les tokens du user_input: {e}")
        return 0


def monitor_agent_call(agent: AtomicAgent[InputSchema, OutputSchema], 
                     user_input: Optional[InputSchema] = None,
                     method: str = "run") -> Tuple[OutputSchema, TokenUsageInfo]:
    """
    Enveloppe un appel SYNCHRONE à un agent AtomicAgent et retourne les informations de tokens.
    
    Args:
        agent: L'agent AtomicAgent à surveiller
        user_input: L'entrée utilisateur pour l'agent (optionnel)
        method: La méthode à appeler sur l'agent ('run', 'run_stream')
    
    Returns:
        Tuple contenant:
        - La réponse de l'agent (OutputSchema)
        - TokenUsageInfo: consommation de l'appel (tokens d'entrée/sortie,
          tokens en cache, source de la mesure) et coût estimé en euros
    
    Example:
        ```python
        from agents.token_monitor import monitor_agent_call
        from agents.qa_agent import get_qa_agent
        
        qa_agent = get_qa_agent()
        user_input = {"message": "Génère 3 questions.", "document": "mon_document"}
        
        # Utilisation avec la méthode run
        response, usage_info = monitor_agent_call(qa_agent, user_input, "run")
        
        print(f"Tokens d'entrée: {usage_info.input_tokens}")
        print(f"Tokens de sortie: {usage_info.output_tokens}")
        if usage_info.cost_eur is not None:
            print(f"Coût estimé: {usage_info.cost_eur} €")
        print(f"Réponse: {response}")
        ```
    """
    # Obtenir le contexte de base (system prompt + historique + outils)
    base_context_result = agent.get_context_token_count()
    
    # Compter les tokens du user_input séparément
    user_input_tokens = _count_user_input_tokens(agent, user_input)
    
    # Calculer le total des tokens d'entrée
    input_tokens_total = base_context_result.total + user_input_tokens
    
    # Stocker la méthode originale
    original_method = getattr(agent, method)
    
    # Appeler la méthode originale (synchrone uniquement)
    if method in ["run", "run_stream"]:
        response = original_method(user_input)
    else:
        raise ValueError(f"Méthode non supportée pour les appels synchrones: {method}. Utilisez monitor_agent_call_async pour les méthodes asynchrones.")
    
    # Compter les tokens de sortie
    output_tokens = _count_output_tokens(agent, response)
    
    usage_info = _usage_info_for(agent, input_tokens_total, output_tokens)
    return response, usage_info


async def monitor_agent_call_async(agent: AtomicAgent[InputSchema, OutputSchema], 
                                user_input: Optional[InputSchema] = None,
                                method: str = "run_async") -> Tuple[OutputSchema, TokenUsageInfo]:
    """
    Enveloppe un appel ASYNCHRONE à un agent AtomicAgent et retourne les informations de tokens.
    
    Args:
        agent: L'agent AtomicAgent à surveiller
        user_input: L'entrée utilisateur pour l'agent (optionnel)
        method: La méthode à appeler sur l'agent ('run_async', 'run_async_stream')
    
    Returns:
        Tuple contenant:
        - La réponse de l'agent (OutputSchema)
        - TokenUsageInfo: consommation de l'appel (tokens d'entrée/sortie,
          tokens en cache, source de la mesure) et coût estimé en euros
    
    Example:
        ```python
        from agents.token_monitor import monitor_agent_call_async
        from agents.qa_agent import get_qa_agent
        
        qa_agent = get_qa_agent()  # Doit être configuré avec un client async
        user_input = {"message": "Génère 3 questions.", "document": "mon_document"}
        
        # Utilisation avec la méthode run_async
        response, usage_info = await monitor_agent_call_async(qa_agent, user_input, "run_async")
        
        print(f"Tokens d'entrée: {usage_info.input_tokens}")
        print(f"Tokens de sortie: {usage_info.output_tokens}")
        if usage_info.cost_eur is not None:
            print(f"Coût estimé: {usage_info.cost_eur} €")
        print(f"Réponse: {response}")
        ```
    """
    # Obtenir le contexte de base (system prompt + historique + outils)
    base_context_result = agent.get_context_token_count()
    
    # Compter les tokens du user_input séparément
    user_input_tokens = _count_user_input_tokens(agent, user_input)
    
    # Calculer le total des tokens d'entrée
    input_tokens_total = base_context_result.total + user_input_tokens
    
    # Stocker la méthode originale
    original_method = getattr(agent, method)
    
    # Appeler la méthode originale (asynchrone uniquement)
    if method in ["run_async", "run_async_stream"]:
        response = await original_method(user_input)
    else:
        raise ValueError(f"Méthode non supportée pour les appels asynchrones: {method}. Utilisez monitor_agent_call pour les méthodes synchrones.")
    
    # Compter les tokens de sortie
    output_tokens = _count_output_tokens(agent, response)
    
    usage_info = _usage_info_for(agent, input_tokens_total, output_tokens)
    return response, usage_info


def _count_output_tokens(agent: AtomicAgent[InputSchema, OutputSchema], 
                       response: OutputSchema) -> int:
    """
    Compte les tokens dans la réponse de l'agent.
    
    Args:
        agent: L'agent AtomicAgent
        response: La réponse de l'agent
    
    Returns:
        Le nombre de tokens dans la réponse
    """
    try:
        # Convertir la réponse en texte pour le comptage
        if hasattr(response, 'model_dump'):
            # Pour les objets Pydantic
            response_text = str(response.model_dump())
        else:
            # Pour les autres types
            response_text = str(response)
        
        # Utiliser le compteur de tokens pour compter les tokens de sortie
        counter = get_token_counter()
        return counter.count_text(agent.model, response_text)
        
    except Exception as e:
        logger.warning(f"Impossible de compter les tokens de sortie: {e}")
        return 0


def token_monitor_decorator(method: Callable) -> Callable:
    """
    Décorateur pour surveiller les appels aux agents et afficher les informations de tokens.
    
    Ce décorateur peut être utilisé pour envelopper les méthodes qui appellent des agents.
    
    Example:
        ```python
        from agents.token_monitor import token_monitor_decorator
        
        @token_monitor_decorator
        def my_function_that_uses_agent():
            response = qa_agent.run(user_input)
            return response
        ```
    """
    @wraps(method)
    def wrapper(*args, **kwargs):
        # Extraire l'agent et l'entrée utilisateur des arguments
        # Cette partie dépend de la signature de la méthode décorée
        # et peut nécessiter des ajustements
        
        # Pour l'instant, nous allons simplement appeler la méthode
        # et essayer de détecter les appels aux agents
        result = method(*args, **kwargs)
        
        # Ici, nous pourrions analyser le résultat et afficher les informations
        # Mais cela nécessite plus de travail pour détecter automatiquement les agents
        
        return result
    
    return wrapper


# Fonction utilitaire pour afficher les informations de tokens de manière formatée
def print_token_info(input_tokens: TokenCountResult, output_tokens: int, 
                    method_name: str = "run"):
    """
    Affiche les informations de tokens de manière formatée.
    
    Args:
        input_tokens: Résultat du comptage de tokens d'entrée (TokenCountResult ou int)
        output_tokens: Nombre de tokens de sortie
        method_name: Nom de la méthode appelée
    """
    print(f"\n{'='*60}")
    print(f"INFORMATIONS DE TOKENS - Méthode: {method_name}")
    print(f"{'='*60}")
    
    # Si input_tokens est un int, afficher juste le total
    if isinstance(input_tokens, int):
        print(f"Tokens d'entrée: {input_tokens}")
        print(f"Tokens de sortie: {output_tokens}")
        print(f"Total (entrée + sortie): {input_tokens + output_tokens}")
    else:
        # Sinon, c'est un TokenCountResult, afficher toutes les informations
        print(f"Modèle: {input_tokens.model}")
        print(f"Tokens d'entrée:")
        print(f"  Total: {input_tokens.total}")
        print(f"  Système: {input_tokens.system_prompt}")
        print(f"  Historique: {input_tokens.history}")
        print(f"  Outils: {input_tokens.tools}")
        if input_tokens.max_tokens:
            print(f"  Utilisation: {input_tokens.utilization:.1%} ({input_tokens.total}/{input_tokens.max_tokens})")
        print(f"Tokens de sortie: {output_tokens}")
        print(f"Total (entrée + sortie): {input_tokens.total + output_tokens}")
    print(f"{'='*60}\n")

def aggregate_token_usage(usage_records) -> Dict[str, Any]:
    """Agrège une liste de métadonnées de consommation en un total consolidé.

    Chaque enregistrement est une métadonnée telle que produite par
    TokenUsageInfo.to_metadata() (input_tokens, output_tokens, cached_tokens,
    cost_eur, cost_detail) ou un dictionnaire équivalent.

    Returns:
        Dictionnaire {calls, input_tokens, output_tokens, cached_tokens,
        total_tokens, cost_eur, cost_available}.
    """
    totals: Dict[str, Any] = {
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 0,
        "cost_eur": 0.0,
        "cost_available": False,
    }
    for record in usage_records or []:
        totals["calls"] += 1
        totals["input_tokens"] += record.get("input_tokens", 0) or 0
        totals["output_tokens"] += record.get("output_tokens", 0) or 0
        totals["cached_tokens"] += record.get("cached_tokens", 0) or 0
        if record.get("cost_eur") is not None:
            totals["cost_eur"] += record["cost_eur"]
            totals["cost_available"] = True
    totals["total_tokens"] = totals["input_tokens"] + totals["output_tokens"]
    totals["cost_eur"] = round(totals["cost_eur"], 6)
    if not totals["cost_available"]:
        totals["cost_eur"] = None
    return totals
