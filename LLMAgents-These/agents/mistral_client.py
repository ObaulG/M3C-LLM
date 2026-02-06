# dependencies.py
import os
import instructor
import mistralai
from fastapi import Depends, HTTPException
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import warnings

# Configurer le logging
logger = logging.getLogger(__name__)

# Variables globales pour le suivi de la consommation API
_api_call_history = []
_api_rate_limits = {}
_api_warnings_issued = set()

class MistralAPIMonitor:
    """
    Classe pour surveiller et gérer la consommation de l'API Mistral.
    
    Cette classe fournit des fonctionnalités pour :
    - Suivre les appels API
    - Vérifier les limites de taux
    - Estimer la consommation
    - Générer des alertes
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.call_history = []
        self.rate_limits = {}
        self.warnings_issued = set()
        
    def track_api_call(self, model: str, input_tokens: int, output_tokens: int, 
                      response_time: float, status: str = "success"):
        """
        Enregistre un appel API dans l'historique.
        
        Args:
            model: Nom du modèle utilisé
            input_tokens: Nombre de tokens en entrée
            output_tokens: Nombre de tokens en sortie
            response_time: Temps de réponse en secondes
            status: Statut de l'appel (success, error, rate_limited, etc.)
        """
        call_record = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "response_time": response_time,
            "status": status
        }
        
        self.call_history.append(call_record)
        _api_call_history.append(call_record)
        
        logger.info(f"API call tracked: {model} - {input_tokens} input, {output_tokens} output tokens")
        
    def get_api_usage(self, time_window: str = "hour") -> Dict[str, Any]:
        """
        Retourne les statistiques d'utilisation de l'API pour une période donnée.
        
        Args:
            time_window: Période pour les statistiques (hour, day, week, month, all)
        
        Returns:
            Dictionnaire contenant les statistiques d'utilisation
        """
        now = datetime.now()
        
        if time_window == "hour":
            cutoff = now - timedelta(hours=1)
        elif time_window == "day":
            cutoff = now - timedelta(days=1)
        elif time_window == "week":
            cutoff = now - timedelta(weeks=1)
        elif time_window == "month":
            cutoff = now - timedelta(days=30)
        else:  # all
            cutoff = now - timedelta(days=365)
        
        recent_calls = [call for call in self.call_history 
                       if datetime.fromisoformat(call["timestamp"]) >= cutoff]
        
        if not recent_calls:
            return {
                "time_window": time_window,
                "total_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "models_used": {},
                "avg_response_time": 0,
                "error_rate": 0
            }
        
        total_calls = len(recent_calls)
        total_input_tokens = sum(call["input_tokens"] for call in recent_calls)
        total_output_tokens = sum(call["output_tokens"] for call in recent_calls)
        total_tokens = sum(call["total_tokens"] for call in recent_calls)
        avg_response_time = sum(call["response_time"] for call in recent_calls) / total_calls
        
        # Statistiques par modèle
        models_used = {}
        for call in recent_calls:
            model = call["model"]
            if model not in models_used:
                models_used[model] = {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0
                }
            models_used[model]["calls"] += 1
            models_used[model]["input_tokens"] += call["input_tokens"]
            models_used[model]["output_tokens"] += call["output_tokens"]
            models_used[model]["total_tokens"] += call["total_tokens"]
        
        # Taux d'erreur
        error_calls = sum(1 for call in recent_calls if call["status"] != "success")
        error_rate = error_calls / total_calls if total_calls > 0 else 0
        
        return {
            "time_window": time_window,
            "total_calls": total_calls,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
            "models_used": models_used,
            "avg_response_time": avg_response_time,
            "error_rate": error_rate,
            "start_time": cutoff.isoformat(),
            "end_time": now.isoformat()
        }
    
    def check_rate_limits(self, model: str, tokens: int) -> Dict[str, Any]:
        """
        Vérifie si un appel API dépasserait les limites de taux connues.
        
        Args:
            model: Nom du modèle
            tokens: Nombre de tokens estimé pour l'appel
        
        Returns:
            Dictionnaire avec le statut et les informations sur les limites
        """
        # Limites connues pour les modèles Mistral (à ajuster selon votre plan)
        # Ces valeurs sont des estimations - vérifiez avec Mistral pour les limites exactes
        known_limits = {
            "mistral-tiny": {"rpm": 1000, "tpm": 500000},
            "mistral-small": {"rpm": 500, "tpm": 300000},
            "mistral-medium": {"rpm": 200, "tpm": 200000},
            "mistral-large": {"rpm": 100, "tpm": 100000},
            "mistral-embed": {"rpm": 1000, "tpm": 1000000}
        }
        
        # Obtenir les statistiques pour la dernière minute
        usage = self.get_api_usage("hour")  # Utiliser hour pour une estimation conservative
        current_calls = usage["total_calls"]
        current_tokens = usage["total_tokens"]
        
        # Obtenir les limites pour le modèle (ou utiliser des valeurs par défaut)
        model_key = model.split("-")[0]  # Extraire la base du modèle (mistral-tiny -> mistral)
        if model_key in known_limits:
            limits = known_limits[model_key]
        else:
            # Valeurs par défaut conservatives
            limits = {"rpm": 100, "tpm": 100000}
            warnings.warn(f"Limites inconnues pour le modèle {model}. Utilisation de valeurs par défaut.")
        
        # Calculer le pourcentage d'utilisation
        rpm_usage = (current_calls / limits["rpm"]) * 100 if limits["rpm"] > 0 else 0
        tpm_usage = (current_tokens / limits["tpm"]) * 100 if limits["tpm"] > 0 else 0
        
        # Générer des alertes si nécessaire
        alert_level = "normal"
        warning_messages = []
        
        if rpm_usage > 90:
            alert_level = "critical"
            warning_messages.append(f"Approche de la limite RPM: {rpm_usage:.1f}% utilisé")
        elif rpm_usage > 75:
            alert_level = "warning"
            warning_messages.append(f"Utilisation élevée RPM: {rpm_usage:.1f}% utilisé")
        
        if tpm_usage > 90:
            alert_level = "critical"
            warning_messages.append(f"Approche de la limite TPM: {tpm_usage:.1f}% utilisé")
        elif tpm_usage > 75:
            alert_level = "warning"
            warning_messages.append(f"Utilisation élevée TPM: {tpm_usage:.1f}% utilisé")
        
        # Estimer le coût (valeurs approximatives en $ par million de tokens)
        pricing = {
            "mistral-tiny": 0.25,
            "mistral-small": 0.50,
            "mistral-medium": 1.00,
            "mistral-large": 2.00,
            "mistral-embed": 0.10
        }
        
        model_price_key = model.split("-")[0]
        price_per_million = pricing.get(model_price_key, 1.00)
        estimated_cost = (tokens / 1_000_000) * price_per_million
        
        return {
            "model": model,
            "current_calls": current_calls,
            "current_tokens": current_tokens,
            "estimated_call_tokens": tokens,
            "rpm_limit": limits["rpm"],
            "tpm_limit": limits["tpm"],
            "rpm_usage_percent": rpm_usage,
            "tpm_usage_percent": tpm_usage,
            "alert_level": alert_level,
            "warning_messages": warning_messages,
            "estimated_cost_usd": estimated_cost,
            "can_make_call": alert_level != "critical"
        }
    
    def get_cost_estimate(self, time_window: str = "day") -> Dict[str, Any]:
        """
        Estime le coût d'utilisation de l'API pour une période donnée.
        
        Args:
            time_window: Période pour l'estimation (hour, day, week, month)
        
        Returns:
            Dictionnaire avec l'estimation des coûts
        """
        usage = self.get_api_usage(time_window)
        
        # Prix approximatifs (en $ par million de tokens)
        pricing = {
            "mistral-tiny": 0.25,
            "mistral-small": 0.50,
            "mistral-medium": 1.00,
            "mistral-large": 2.00,
            "mistral-embed": 0.10
        }
        
        total_cost = 0
        model_costs = {}
        
        for model, stats in usage["models_used"].items():
            model_key = model.split("-")[0]
            price_per_million = pricing.get(model_key, 1.00)
            model_cost = (stats["total_tokens"] / 1_000_000) * price_per_million
            total_cost += model_cost
            model_costs[model] = {
                "tokens": stats["total_tokens"],
                "cost_usd": model_cost,
                "price_per_million": price_per_million
            }
        
        return {
            "time_window": time_window,
            "total_cost_usd": total_cost,
            "model_costs": model_costs,
            "total_tokens": usage["total_tokens"],
            "start_time": usage["start_time"],
            "end_time": usage["end_time"]
        }
    
    def reset_monitor(self):
        """Réinitialise le moniteur (utile pour les tests)."""
        self.call_history = []
        self.warnings_issued = set()


# Instance globale du moniteur (optionnel)
_global_api_monitor = None


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
    
    # Initialiser le moniteur global si ce n'est pas déjà fait
    global _global_api_monitor
    if _global_api_monitor is None:
        _global_api_monitor = MistralAPIMonitor(MISTRAL_API_KEY)
    
    return client


def get_api_monitor() -> MistralAPIMonitor:
    """
    Retourne l'instance globale du moniteur API.
    
    Returns:
        Instance de MistralAPIMonitor pour surveiller la consommation API
    """
    global _global_api_monitor
    if _global_api_monitor is None:
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
        if not MISTRAL_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="La clé API Mistral n'est pas définie."
            )
        _global_api_monitor = MistralAPIMonitor(MISTRAL_API_KEY)
    return _global_api_monitor


def track_api_call(model: str, input_tokens: int, output_tokens: int, 
                  response_time: float, status: str = "success"):
    """
    Fonction utilitaire pour suivre un appel API.
    
    Args:
        model: Nom du modèle utilisé
        input_tokens: Nombre de tokens en entrée
        output_tokens: Nombre de tokens en sortie
        response_time: Temps de réponse en secondes
        status: Statut de l'appel
    """
    monitor = get_api_monitor()
    monitor.track_api_call(model, input_tokens, output_tokens, response_time, status)


def check_api_limits(model: str, estimated_tokens: int) -> Dict[str, Any]:
    """
    Vérifie les limites de l'API avant de faire un appel.
    
    Args:
        model: Nom du modèle
        estimated_tokens: Nombre de tokens estimés pour l'appel
    
    Returns:
        Dictionnaire avec les informations sur les limites et alertes
    """
    monitor = get_api_monitor()
    return monitor.check_rate_limits(model, estimated_tokens)


def get_current_api_usage(time_window: str = "hour") -> Dict[str, Any]:
    """
    Retourne l'utilisation actuelle de l'API.
    
    Args:
        time_window: Période pour les statistiques
    
    Returns:
        Statistiques d'utilisation de l'API
    """
    monitor = get_api_monitor()
    return monitor.get_api_usage(time_window)


def get_cost_estimate(time_window: str = "day") -> Dict[str, Any]:
    """
    Estime le coût d'utilisation de l'API.
    
    Args:
        time_window: Période pour l'estimation
    
    Returns:
        Estimation des coûts
    """
    monitor = get_api_monitor()
    return monitor.get_cost_estimate(time_window)
