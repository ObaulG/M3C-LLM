# agents/token_monitor.py
"""
Utilitaire pour surveiller et afficher le nombre de tokens en entrée et en sortie
lors des appels aux agents AtomicAgent.

Cet utilitaire peut être utilisé pour envelopper les appels aux agents et fournir
des informations détaillées sur l'utilisation des tokens.
"""

from typing import TypeVar, Any, Callable, Optional, Tuple
from atomic_agents import AtomicAgent, BaseIOSchema
from atomic_agents.utils.token_counter import get_token_counter, TokenCountResult
import logging
from functools import wraps

# Type variables pour les schémas d'entrée/sortie
InputSchema = TypeVar('InputSchema', bound=BaseIOSchema)
OutputSchema = TypeVar('OutputSchema', bound=BaseIOSchema)

logger = logging.getLogger(__name__)


def monitor_agent_call(agent: AtomicAgent[InputSchema, OutputSchema], 
                     user_input: Optional[InputSchema] = None,
                     method: str = "run") -> Tuple[OutputSchema, TokenCountResult, int]:
    """
    Enveloppe un appel SYNCHRONE à un agent AtomicAgent et retourne les informations de tokens.
    
    Args:
        agent: L'agent AtomicAgent à surveiller
        user_input: L'entrée utilisateur pour l'agent (optionnel)
        method: La méthode à appeler sur l'agent ('run', 'run_stream')
    
    Returns:
        Tuple contenant:
        - La réponse de l'agent (OutputSchema)
        - Le résultat du comptage de tokens d'entrée (TokenCountResult)
        - Le nombre de tokens de sortie (int)
    
    Example:
        ```python
        from agents.token_monitor import monitor_agent_call
        from agents.qa_agent import get_qa_agent
        
        qa_agent = get_qa_agent()
        user_input = {"message": "Génère 3 questions.", "document": "mon_document"}
        
        # Utilisation avec la méthode run
        response, input_tokens, output_tokens = monitor_agent_call(qa_agent, user_input, "run")
        
        print(f"Tokens d'entrée: {input_tokens.total}")
        print(f"Tokens de sortie: {output_tokens}")
        print(f"Réponse: {response}")
        ```
    """
    # Compter les tokens d'entrée avant l'appel
    input_token_result = agent.get_context_token_count()
    
    # Stocker la méthode originale
    original_method = getattr(agent, method)
    
    # Appeler la méthode originale (synchrone uniquement)
    if method in ["run", "run_stream"]:
        response = original_method(user_input)
    else:
        raise ValueError(f"Méthode non supportée pour les appels synchrones: {method}. Utilisez monitor_agent_call_async pour les méthodes asynchrones.")
    
    # Compter les tokens de sortie
    output_tokens = _count_output_tokens(agent, response)
    
    return response, input_token_result, output_tokens


async def monitor_agent_call_async(agent: AtomicAgent[InputSchema, OutputSchema], 
                                user_input: Optional[InputSchema] = None,
                                method: str = "run_async") -> Tuple[OutputSchema, TokenCountResult, int]:
    """
    Enveloppe un appel ASYNCHRONE à un agent AtomicAgent et retourne les informations de tokens.
    
    Args:
        agent: L'agent AtomicAgent à surveiller
        user_input: L'entrée utilisateur pour l'agent (optionnel)
        method: La méthode à appeler sur l'agent ('run_async', 'run_async_stream')
    
    Returns:
        Tuple contenant:
        - La réponse de l'agent (OutputSchema)
        - Le résultat du comptage de tokens d'entrée (TokenCountResult)
        - Le nombre de tokens de sortie (int)
    
    Example:
        ```python
        from agents.token_monitor import monitor_agent_call_async
        from agents.qa_agent import get_qa_agent
        
        qa_agent = get_qa_agent()  # Doit être configuré avec un client async
        user_input = {"message": "Génère 3 questions.", "document": "mon_document"}
        
        # Utilisation avec la méthode run_async
        response, input_tokens, output_tokens = await monitor_agent_call_async(qa_agent, user_input, "run_async")
        
        print(f"Tokens d'entrée: {input_tokens.total}")
        print(f"Tokens de sortie: {output_tokens}")
        print(f"Réponse: {response}")
        ```
    """
    # Compter les tokens d'entrée avant l'appel
    input_token_result = agent.get_context_token_count()
    
    # Stocker la méthode originale
    original_method = getattr(agent, method)
    
    # Appeler la méthode originale (asynchrone uniquement)
    if method in ["run_async", "run_async_stream"]:
        response = await original_method(user_input)
    else:
        raise ValueError(f"Méthode non supportée pour les appels asynchrones: {method}. Utilisez monitor_agent_call pour les méthodes synchrones.")
    
    # Compter les tokens de sortie
    output_tokens = _count_output_tokens(agent, response)
    
    return response, input_token_result, output_tokens


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
        input_tokens: Résultat du comptage de tokens d'entrée
        output_tokens: Nombre de tokens de sortie
        method_name: Nom de la méthode appelée
    """
    print(f"\n{'='*60}")
    print(f"INFORMATIONS DE TOKENS - Méthode: {method_name}")
    print(f"{'='*60}")
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