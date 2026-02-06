# Surveillance des Tokens avec Atomic Agents

Ce guide explique comment utiliser le moniteur de tokens pour surveiller l'utilisation des tokens lors des appels aux agents AtomicAgent.

## Introduction

Le moniteur de tokens permet de mesurer et d'afficher le nombre de tokens utilisés en entrée et en sortie lors des appels aux agents. Cela est utile pour :

- **Optimiser les coûts** : Comprendre l'utilisation des tokens pour mieux gérer les budgets
- **Déboguer** : Identifier les appels qui consomment trop de tokens
- **Surveiller** : Suivre l'utilisation des ressources au fil du temps
- **Améliorer** : Optimiser les prompts et les réponses pour réduire la consommation

## Installation

Le moniteur de tokens est déjà intégré dans le projet. Aucune installation supplémentaire n'est nécessaire.

## Utilisation de Base

### Appels Synchrones

Pour les appels synchrones (méthodes `run` et `run_stream`), utilisez `monitor_agent_call` :

```python
from agents.token_monitor import monitor_agent_call, print_token_info
from agents.qa_agent import get_qa_agent, QuestionRequestInput

# Initialiser l'agent
qa_agent = get_qa_agent(model="mistral-medium")

# Créer l'entrée utilisateur
user_input = QuestionRequestInput(
    message="Génère 3 questions sur l'intelligence artificielle.",
    document="L'intelligence artificielle est une technologie..."
)

# Appeler l'agent avec surveillance des tokens
response, input_tokens, output_tokens = monitor_agent_call(
    agent=qa_agent,
    user_input=user_input
)

# Afficher les informations de tokens
print_token_info(input_tokens, output_tokens, "run")

# Utiliser la réponse normalement
print(f"Nombre de questions: {len(response.questions_answers)}")
```

### Appels Asynchrones

Pour les appels asynchrones (méthodes `run_async` et `run_async_stream`), utilisez `monitor_agent_call_async` :

```python
from agents.token_monitor import monitor_agent_call_async, print_token_info
from agents.qa_agent import get_qa_agent, QuestionRequestInput

# Initialiser l'agent avec un client async
qa_agent = get_qa_agent(model="mistral-medium")  # Assurez-vous que le client est async

# Créer l'entrée utilisateur
user_input = QuestionRequestInput(
    message="Génère 3 questions sur l'intelligence artificielle.",
    document="L'intelligence artificielle est une technologie..."
)

# Appeler l'agent avec surveillance des tokens (async)
response, input_tokens, output_tokens = await monitor_agent_call_async(
    agent=qa_agent,
    user_input=user_input
)

# Afficher les informations de tokens
print_token_info(input_tokens, output_tokens, "run_async")
```

## Intégration dans le Code Existant

### Avant (sans surveillance)

```python
# Code original dans api_server.py
@app.post("/api/sessions/init/{document_id}")
async def init_session(document_id: str):
    # Générer les questions/réponses pour le document
    response = qa_agent.run({"message": "Génère 3 questions.", "document": document_id})
    
    # Créer une nouvelle session
    session_id = str(uuid.uuid4())
    session_manager.create_session(session_id, document_id)
    session_manager.add_questions(session_id, response.questions_answers)
    
    return {
        "session_id": session_id,
        "document_id": document_id,
        "questions": response.questions_answers,
    }
```

### Après (avec surveillance)

```python
# Code modifié avec surveillance des tokens
from agents.token_monitor import monitor_agent_call, print_token_info

@app.post("/api/sessions/init/{document_id}")
async def init_session(document_id: str):
    # Initialiser l'agent QA
    qa_agent = get_qa_agent()
    
    # Créer l'entrée utilisateur
    user_input = QuestionRequestInput(
        message="Génère 3 questions.",
        document=document_id
    )
    
    # Appeler l'agent avec surveillance des tokens
    response, input_tokens, output_tokens = monitor_agent_call(
        agent=qa_agent,
        user_input=user_input
    )
    
    # Afficher les informations de tokens (optionnel)
    print_token_info(input_tokens, output_tokens, "run")
    
    # Créer une nouvelle session
    session_id = str(uuid.uuid4())
    session_manager.create_session(session_id, document_id)
    session_manager.add_questions(session_id, response.questions_answers)
    
    # Retourner les informations de tokens (optionnel)
    return {
        "session_id": session_id,
        "document_id": document_id,
        "questions": response.questions_answers,
        "token_usage": {
            "input_tokens": input_tokens.total,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens.total + output_tokens,
            "model": input_tokens.model
        }
    }
```

## Fonctions Disponibles

### `monitor_agent_call()`

Enveloppe un appel SYNCHRONE à un agent AtomicAgent.

**Paramètres:**
- `agent`: L'agent AtomicAgent à surveiller
- `user_input`: L'entrée utilisateur pour l'agent (optionnel)
- `method`: La méthode à appeler (`"run"` ou `"run_stream"`, par défaut `"run"`)

**Retourne:**
- `Tuple[OutputSchema, TokenCountResult, int]`: La réponse, les tokens d'entrée, les tokens de sortie

### `monitor_agent_call_async()`

Enveloppe un appel ASYNCHRONE à un agent AtomicAgent.

**Paramètres:**
- `agent`: L'agent AtomicAgent à surveiller
- `user_input`: L'entrée utilisateur pour l'agent (optionnel)
- `method`: La méthode à appeler (`"run_async"` ou `"run_async_stream"`, par défaut `"run_async"`)

**Retourne:**
- `Tuple[OutputSchema, TokenCountResult, int]`: La réponse, les tokens d'entrée, les tokens de sortie

### `print_token_info()`

Affiche les informations de tokens de manière formatée.

**Paramètres:**
- `input_tokens`: Résultat du comptage de tokens d'entrée (TokenCountResult)
- `output_tokens`: Nombre de tokens de sortie (int)
- `method_name`: Nom de la méthode appelée (par défaut `"run"`)

## Structure des Tokens

Le `TokenCountResult` contient les informations suivantes :

- `total`: Nombre total de tokens d'entrée
- `system_prompt`: Tokens utilisés par le prompt système
- `history`: Tokens utilisés par l'historique de conversation
- `tools`: Tokens utilisés par les définitions d'outils
- `model`: Nom du modèle utilisé
- `max_tokens`: Taille maximale du contexte (si connue)
- `utilization`: Pourcentage d'utilisation du contexte (si max_tokens est connu)

## Exemple de Sortie

```
============================================================
INFORMATIONS DE TOKENS - Méthode: run
============================================================
Modèle: mistral-medium
Tokens d'entrée:
  Total: 202
  Système: 161
  Historique: 0
  Outils: 41
Tokens de sortie: 231
Total (entrée + sortie): 433
============================================================
```

## Bonnes Pratiques

1. **Utilisation Sélective** : Activez la surveillance uniquement lorsque nécessaire pour éviter les overheads
2. **Journalisation** : Enregistrez les informations de tokens dans des logs pour le suivi
3. **Seuils** : Définissez des seuils d'alerte pour les appels qui consomment trop de tokens
4. **Optimisation** : Utilisez les données pour optimiser vos prompts et réduire les coûts

## Limitations

- Le comptage des tokens de sortie est une estimation basée sur la réponse textuelle
- Certains modèles peuvent ne pas être reconnus par litellm (warning normal)
- Les appels asynchrones nécessitent un client Instructor configuré en mode async

## Support

Pour toute question ou problème, consultez la documentation de la librairie atomic_agents ou contactez l'équipe de développement.