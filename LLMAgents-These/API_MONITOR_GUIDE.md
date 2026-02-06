# Guide de Surveillance de la Consommation API Mistral

Ce guide explique comment utiliser les nouvelles fonctions ajoutées à `mistral_client.py` pour surveiller et gérer la consommation de votre clé API Mistral, afin d'éviter de dépasser les limites.

## 🎯 Problème Résolu

Vous dépassiez fréquemment la limite de l'API en résumant des documents. Les nouvelles fonctions permettent de :

- **Surveiller** la consommation en temps réel
- **Prévenir** les dépassements de limite
- **Estimer** les coûts d'utilisation
- **Optimiser** l'utilisation des ressources

## 📁 Fichiers Modifiés/ajoutés

1. **`agents/mistral_client.py`** - Fonctions principales ajoutées
2. **`api_monitor_demo.py`** - Démonstration complète
3. **`API_MONITOR_GUIDE.md`** - Ce guide

## 🔧 Fonctions Disponibles

### 1. `get_api_monitor() -> MistralAPIMonitor`

Retourne l'instance globale du moniteur API.

```python
from agents.mistral_client import get_api_monitor

monitor = get_api_monitor()
```

### 2. `track_api_call(model, input_tokens, output_tokens, response_time, status)`

Enregistre un appel API dans l'historique.

```python
from agents.mistral_client import track_api_call

track_api_call(
    model="mistral-medium",
    input_tokens=500,
    output_tokens=250,
    response_time=1.2,
    status="success"
)
```

### 3. `check_api_limits(model, estimated_tokens) -> Dict`

Vérifie si un appel dépasserait les limites de taux.

```python
from agents.mistral_client import check_api_limits

check_result = check_api_limits("mistral-medium", estimated_tokens=1000)
if not check_result['can_make_call']:
    print("⚠️  Ne pas faire l'appel!")
```

### 4. `get_current_api_usage(time_window) -> Dict`

Retourne les statistiques d'utilisation.

```python
from agents.mistral_client import get_current_api_usage

usage = get_current_api_usage("hour")  # hour, day, week, month
print(f"Appels: {usage['total_calls']}, Tokens: {usage['total_tokens']}")
```

### 5. `get_cost_estimate(time_window) -> Dict`

Estime le coût d'utilisation.

```python
from agents.mistral_client import get_cost_estimate

cost_data = get_cost_estimate("day")
print(f"Coût aujourd'hui: ${cost_data['total_cost_usd']:.4f}")
```

## 📊 Intégration dans le Code Existant

### Avant (sans surveillance)

```python
# Code original qui pouvait dépasser les limites
qa_agent = get_qa_agent()
response = qa_agent.run(user_input)
```

### Après (avec surveillance)

```python
# Code modifié avec prévention des dépassements
from agents.mistral_client import check_api_limits, track_api_call
from agents.token_monitor import monitor_agent_call
import time

# 1. Vérifier les limites avant l'appel
check_result = check_api_limits("mistral-medium", estimated_tokens=500)

if not check_result['can_make_call']:
    print(f"⚠️  ALERTE: {check_result['warning_messages']}")
    # Gérer l'erreur ou attendre
    return

# 2. Faire l'appel avec surveillance des tokens
start_time = time.time()
response, input_tokens, output_tokens = monitor_agent_call(
    agent=qa_agent,
    user_input=user_input
)

# 3. Enregistrer l'appel
response_time = time.time() - start_time
track_api_call(
    model="mistral-medium",
    input_tokens=input_tokens.total,
    output_tokens=output_tokens,
    response_time=response_time,
    status="success"
)
```

## 🛡️ Prévention des Dépassements de Limite

### Exemple Complet

```python
def safe_api_call(agent, user_input, model, estimated_tokens):
    """Fonction wrapper pour les appels API sûrs."""
    
    # 1. Vérifier les limites
    check_result = check_api_limits(model, estimated_tokens)
    
    if not check_result['can_make_call']:
        logger.warning(f"API limit approached: {check_result['warning_messages']}")
        raise APILimitError(f"Cannot make API call: {check_result['warning_messages']}")
    
    # 2. Faire l'appel
    start_time = time.time()
    response, input_tokens, output_tokens = monitor_agent_call(
        agent=agent,
        user_input=user_input
    )
    
    # 3. Enregistrer l'appel
    response_time = time.time() - start_time
    track_api_call(
        model=model,
        input_tokens=input_tokens.total,
        output_tokens=output_tokens,
        response_time=response_time,
        status="success"
    )
    
    return response

class APILimitError(Exception):
    """Exception pour les limites API."""
    pass
```

## 📈 Surveillance en Temps Réel

### Tableau de Bord Simple

```python
def print_api_dashboard():
    """Affiche un tableau de bord de l'utilisation API."""
    
    print("\n" + "="*60)
    print("TABLEAU DE BORD API MISTRAL")
    print("="*60)
    
    # Utilisation actuelle
    usage_hour = get_current_api_usage("hour")
    usage_day = get_current_api_usage("day")
    
    print(f"📊 Dernière heure:")
    print(f"   Appels: {usage_hour['total_calls']}")
    print(f"   Tokens: {usage_hour['total_tokens']}")
    print(f"   Temps moyen: {usage_hour['avg_response_time']:.2f}s")
    
    print(f"\n📊 Aujourd'hui:")
    print(f"   Appels: {usage_day['total_calls']}")
    print(f"   Tokens: {usage_day['total_tokens']}")
    print(f"   Erreurs: {usage_day['error_rate']*100:.1f}%")
    
    # Vérification des limites
    check_result = check_api_limits("mistral-medium", estimated_tokens=1000)
    
    print(f"\n⚠️  Alertes:")
    print(f"   Niveau: {check_result['alert_level']}")
    if check_result['warning_messages']:
        for msg in check_result['warning_messages']:
            print(f"   - {msg}")
    else:
        print(f"   Aucune alerte active")
    
    # Estimation des coûts
    cost_data = get_cost_estimate("day")
    print(f"\n💰 Coûts:")
    print(f"   Aujourd'hui: ${cost_data['total_cost_usd']:.4f}")
    print(f"   Par modèle:")
    for model, data in cost_data['model_costs'].items():
        print(f"      {model}: ${data['cost_usd']:.4f}")
    
    print("="*60)
```

## 💰 Gestion des Coûts

### Analyse des Coûts par Modèle

```python
def analyze_model_costs():
    """Analyse les coûts par modèle."""
    
    cost_data = get_cost_estimate("week")
    
    print("\n📊 Analyse des coûts par modèle (semaine):")
    print("-" * 50)
    
    for model, data in cost_data['model_costs'].items():
        print(f"{model}:")
        print(f"  Tokens: {data['tokens']}")
        print(f"  Coût: ${data['cost_usd']:.4f}")
        print(f"  Prix/M: ${data['price_per_million']}")
        print(f"  % du total: {(data['cost_usd'] / cost_data['total_cost_usd'] * 100):.1f}%")
        print()
    
    print(f"Total: ${cost_data['total_cost_usd']:.4f}")
```

## 🔍 Bonnes Pratiques

### 1. Vérification Avant Chaque Appel Important

```python
# Toujours vérifier avant les appels gourmands
check_result = check_api_limits(model, estimated_tokens)
if not check_result['can_make_call']:
    # Gérer l'erreur ou attendre
    time.sleep(60)  # Attendre 1 minute
    return
```

### 2. Surveillance Régulière

```python
# Dans une tâche cron ou un thread séparé
def monitor_api_usage():
    while True:
        usage = get_current_api_usage("hour")
        if usage['total_calls'] > 150:  # Seuil personnalisé
            send_alert("Utilisation élevée de l'API!")
        time.sleep(300)  # Vérifier toutes les 5 minutes
```

### 3. Journalisation

```python
# Enregistrer les données pour l'analyse
def log_api_usage():
    usage = get_current_api_usage("day")
    cost = get_cost_estimate("day")
    
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "calls": usage['total_calls'],
        "tokens": usage['total_tokens'],
        "cost": cost['total_cost_usd'],
        "models": list(usage['models_used'].keys())
    }
    
    with open("api_usage_log.jsonl", "a") as f:
        f.write(json.dumps(log_data) + "\n")
```

### 4. Gestion des Erreurs

```python
try:
    # Code avec appel API
    response = safe_api_call(agent, user_input, model, estimated_tokens)
except APILimitError as e:
    logger.error(f"Limite API atteinte: {e}")
    # Stratégies de récupération:
    # 1. Attendre et réessayer
    # 2. Utiliser un modèle moins gourmand
    # 3. Mettre en file d'attente pour plus tard
    # 4. Notifier l'administrateur
```

## 📊 Limites Connues

Les limites par défaut utilisées dans le code :

| Modèle | RPM (Requêtes/Min) | TPM (Tokens/Min) |
|--------|-------------------|------------------|
| mistral-tiny | 1000 | 500,000 |
| mistral-small | 500 | 300,000 |
| mistral-medium | 200 | 200,000 |
| mistral-large | 100 | 100,000 |
| mistral-embed | 1000 | 1,000,000 |

⚠️ **Important** : Ces valeurs sont des estimations. Vérifiez avec Mistral pour obtenir les limites exactes de votre compte.

## 🛠️ Personnalisation

### Modifier les Limites

```python
# Dans votre code, vous pouvez créer une instance personnalisée
monitor = MistralAPIMonitor("votre_api_key")

# Et modifier les limites connues
monitor.rate_limits = {
    "mistral-medium": {"rpm": 300, "tpm": 250000},  # Limites personnalisées
}
```

### Ajouter des Modèles

```python
# Pour ajouter un modèle personnalisé
known_limits = monitor.rate_limits
known_limits["mon-modele"] = {"rpm": 50, "tpm": 50000}
```

## 💡 Stratégies pour Éviter les Limites

### 1. Batch Processing

```python
# Regrouper les petites requêtes
def batch_process(questions):
    """Traite les questions par lots."""
    batch_size = 5
    for i in range(0, len(questions), batch_size):
        batch = questions[i:i+batch_size]
        # Traiter le batch
        check_limits_before_batch(batch)
        process_batch(batch)
        time.sleep(10)  # Pause entre les batches
```

### 2. Backoff Exponentiel

```python
def exponential_backoff(retry_count):
    """Attend avec backoff exponentiel."""
    wait_time = min(2 ** retry_count, 60)  # Max 60 secondes
    print(f"Attente de {wait_time} secondes...")
    time.sleep(wait_time)
```

### 3. File d'Attente

```python
# Utiliser une file d'attente pour les requêtes
from queue import Queue

request_queue = Queue()

def worker():
    while True:
        request = request_queue.get()
        try:
            if can_make_call(request['model'], request['tokens']):
                process_request(request)
        except APILimitError:
            request_queue.put(request)  # Remettre dans la file
            time.sleep(60)
        finally:
            request_queue.task_done()
```

### 4. Priorisation

```python
# Prioriser les requêtes importantes
def prioritize_requests(requests):
    high_priority = [r for r in requests if r['priority'] == 'high']
    low_priority = [r for r in requests if r['priority'] == 'low']
    
    # Traiter les requêtes haute priorité en premier
    for request in high_priority:
        process_with_retry(request)
    
    # Traiter les requêtes basse priorité plus tard
    for request in low_priority:
        if not at_limit():
            process_with_retry(request)
```

## 📚 Référence Complète

### Méthodes de MistralAPIMonitor

- `track_api_call(model, input_tokens, output_tokens, response_time, status)`
- `get_api_usage(time_window)` - hour, day, week, month, all
- `check_rate_limits(model, tokens)`
- `get_cost_estimate(time_window)`
- `reset_monitor()`

### Fonctions Utilitaires

- `get_api_monitor()` - Instance globale
- `track_api_call()` - Enregistrement
- `check_api_limits()` - Vérification
- `get_current_api_usage()` - Statistiques
- `get_cost_estimate()` - Estimation des coûts

## 🎉 Conclusion

Avec ces nouvelles fonctions, vous pouvez maintenant :

✅ **Surveiller** la consommation API en temps réel
✅ **Prévenir** les dépassements de limite avant qu'ils ne se produisent
✅ **Estimer** les coûts d'utilisation pour mieux budgétiser
✅ **Optimiser** l'utilisation des ressources API
✅ **Gérer** les erreurs et les files d'attente de manière intelligente

### Intégration Recommandée

1. **Ajoutez la vérification** avant chaque appel API important
2. **Enregistrez tous les appels** avec `track_api_call()`
3. **Surveillez régulièrement** l'utilisation avec `get_current_api_usage()`
4. **Analysez les coûts** quotidiennement avec `get_cost_estimate()`
5. **Configurez des alertes** pour les niveaux critiques

### Exemple d'Intégration Complète

```python
from agents.mistral_client import check_api_limits, track_api_call
from agents.token_monitor import monitor_agent_call
import time

def safe_summarize(document_id, document_path):
    """Fonction de résumé avec surveillance API."""
    
    # 1. Initialiser
    summariser = TokenMonitoringSummariser("mistral-medium")
    
    # 2. Vérifier les limites avant de commencer
    check_result = check_api_limits("mistral-medium", estimated_tokens=5000)
    if not check_result['can_make_call']:
        raise APILimitError(f"Cannot start summarization: {check_result['warning_messages']}")
    
    # 3. Résumer avec surveillance
    try:
        summary = summariser.summarise_with_token_monitoring(document_id, document_path)
        
        # 4. Enregistrer l'appel global
        track_api_call(
            model="mistral-medium",
            input_tokens=summariser.total_input_tokens,
            output_tokens=summariser.total_output_tokens,
            response_time=summariser.call_count * 2.0,  # Estimation
            status="success"
        )
        
        return summary
        
    except Exception as e:
        track_api_call(
            model="mistral-medium",
            input_tokens=summariser.total_input_tokens,
            output_tokens=0,
            response_time=summariser.call_count * 2.0,
            status="error"
        )
        raise
```

Avec cette intégration, vous devriez pouvoir éviter les dépassements de limite tout en ayant une visibilité complète sur votre utilisation de l'API Mistral.