# Guide d'Intégration du Moniteur de Tokens pour le Résumé

Ce guide explique comment intégrer le moniteur de tokens dans le processus de résumé de documents.

## 🎯 Objectif

Ajouter la surveillance des tokens au processus de résumé pour mesurer et optimiser l'utilisation des ressources.

## 📁 Fichiers Disponibles

1. **`summarisation_test_with_tokens.py`** - Approche recommandée (classe étendue)
2. **`summarisation_test_modified.py`** - Approche alternative (wrapper)
3. **`summarisation_token_demo.py`** - Démonstration simplifiée

## 🏆 Approche Recommandée : Classe Étendue

### Avantages

- **Propre et maintenable** : Utilise l'héritage OOP
- **Non intrusive** : Ne modifie pas la classe `Summariser` originale
- **Complète** : Fournit toutes les statistiques nécessaires
- **Flexible** : Peut être utilisée sélectivement

### Utilisation

```python
from summarisation_test_with_tokens import TokenMonitoringSummariser

# Initialiser avec surveillance des tokens
summariser = TokenMonitoringSummariser("mistral-large-latest")

# Résumer avec surveillance
summary = summariser.summarise_with_token_monitoring(DOCUMENT_ID, document_path)

# Afficher les statistiques
total_tokens = summariser.total_input_tokens + summariser.total_output_tokens
print(f"Tokens totaux utilisés: {total_tokens}")

# Afficher un résumé complet
summariser.print_token_summary()
```

### Exemple Complet

```python
import os
from summarisation_test_with_tokens import TokenMonitoringSummariser

# Configuration
DOCUMENT_ID = "votre_document.pdf"
FOLDER = "/chemin/vers/les/documents"

# 1. Initialiser le summariser avec surveillance
summariser = TokenMonitoringSummariser("mistral-large-latest")

# 2. Résumer le document
document_path = os.path.join(FOLDER, DOCUMENT_ID)
summary = summariser.summarise_with_token_monitoring(DOCUMENT_ID, document_path)

# 3. Afficher le résumé
print("Résumé final:")
print(summary)

# 4. Afficher les statistiques de tokens
summariser.print_token_summary()

# 5. Accéder aux données brutes (optionnel)
print(f"Appels totaux: {summariser.call_count}")
print(f"Tokens entrée: {summariser.total_input_tokens}")
print(f"Tokens sortie: {summariser.total_output_tokens}")
```

## 📊 Informations Fournies

Le moniteur de tokens fournit les informations suivantes :

### Par Appel
- Tokens d'entrée pour chaque appel
- Tokens de sortie pour chaque appel
- Type d'agent utilisé (summariser, merger, merger+context)

### Globalement
- **Nombre total d'appels** : Combien de fois les agents ont été appelés
- **Tokens d'entrée totaux** : Somme de tous les tokens d'entrée
- **Tokens de sortie totaux** : Somme de tous les tokens de sortie
- **Tokens totaux** : Entrée + sortie
- **Ratio sortie/entrée** : Efficacité de la compression

### Exemple de Sortie

```
============================================================
RÉSUMÉ DE L'UTILISATION DES TOKENS
============================================================
Modèle utilisé: mistral-large-latest
Nombre total d'appels aux agents: 15
Tokens d'entrée totaux: 45872
Tokens de sortie totaux: 12456
Tokens totaux (entrée + sortie): 58328
Ratio sortie/entrée: 0.27
============================================================
```

## 🔧 Intégration dans le Code Existant

### Avant (sans surveillance)

```python
# summarisation_test.py original
def main():
    summariser = Summariser("mistral-large-latest")
    summary = summariser.summarise(DOCUMENT_ID, document_path)
    print(summary)
```

### Après (avec surveillance)

```python
# summarisation_test.py modifié
def main():
    summariser = TokenMonitoringSummariser("mistral-large-latest")
    summary = summariser.summarise_with_token_monitoring(DOCUMENT_ID, document_path)
    print(summary)
    summariser.print_token_summary()  # Ajouté
```

## 📈 Analyse des Résultats

### Interprétation du Ratio Sortie/Entrée

- **Ratio > 1.5** : La sortie est très détaillée. Vous pourriez optimiser les prompts.
- **Ratio 0.5 - 1.5** : Bon équilibre entre détail et concision.
- **Ratio < 0.5** : La sortie est très concise. Vous pourriez obtenir plus d'informations.

### Surveillance des Coûts

- **< 1000 tokens** : Consommation très faible
- **1000 - 10000 tokens** : Consommation normale
- **> 10000 tokens** : Consommation élevée - surveillance recommandée

## 🎯 Cas d'Utilisation

### 1. Optimisation des Coûts

```python
# Comparer différents modèles
models = ["mistral-medium", "mistral-large-latest"]
for model in models:
    summariser = TokenMonitoringSummariser(model)
    summary = summariser.summarise_with_token_monitoring(DOCUMENT_ID, document_path)
    print(f"{model}: {summariser.total_input_tokens + summariser.total_output_tokens} tokens")
```

### 2. Journalisation

```python
import logging
from datetime import datetime

# Configurer le logging
logging.basicConfig(filename='token_usage.log', level=logging.INFO)

# Après chaque résumé
log_data = {
    "timestamp": datetime.now().isoformat(),
    "document": DOCUMENT_ID,
    "model": summariser.model,
    "input_tokens": summariser.total_input_tokens,
    "output_tokens": summariser.total_output_tokens,
    "total_tokens": summariser.total_input_tokens + summariser.total_output_tokens,
    "call_count": summariser.call_count
}

logging.info("Token usage: %s", log_data)
```

### 3. Surveillance en Temps Réel

```python
# Afficher les tokens pendant le traitement
def custom_summarise_with_monitoring(self, document_id, document_path):
    # ... code existant ...
    
    for i, chunk in enumerate(chunks):
        # ... code existant ...
        
        response, input_tokens, output_tokens = monitor_agent_call(
            agent=self.summariser,
            user_input=user_input
        )
        
        # Affichage personnalisé
        print(f"Chunk {i+1}: Entrée={input_tokens.total} | Sortie={output_tokens} | Total={input_tokens.total + output_tokens}")
        
        # ... reste du code ...
```

## 🛠️ Personnalisation

### Modifier le Format de Sortie

```python
# Dans votre code
def custom_token_summary(self):
    """Format personnalisé pour les rapports."""
    print(f"Rapport d'utilisation des tokens - {datetime.now()}")
    print(f"Document: {DOCUMENT_ID}")
    print(f"Modèle: {self.model}")
    print(f"Coût estimé: ${(self.total_input_tokens + self.total_output_tokens) * 0.0001:.2f}")
    print(f"Efficacité: {100 * self.total_output_tokens / self.total_input_tokens:.1f}%")
```

### Ajouter des Seuils d'Alerte

```python
# Après le résumé
total_tokens = summariser.total_input_tokens + summariser.total_output_tokens

if total_tokens > 15000:
    print("⚠️  ALERTE: Consommation élevée de tokens!")
    # Envoyer une notification, journaliser, etc.
elif total_tokens > 10000:
    print("⚠️  ATTENTION: Consommation modérée de tokens.")
else:
    print("✅ Consommation normale de tokens.")
```

## 💡 Bonnes Pratiques

1. **Utilisation Sélective** : Activez la surveillance uniquement lorsque nécessaire
2. **Journalisation** : Enregistrez les données pour l'analyse à long terme
3. **Comparaison** : Testez différents modèles et paramètres
4. **Optimisation** : Utilisez les données pour améliorer les prompts
5. **Surveillance** : Définissez des seuils d'alerte pour les coûts

## 🔍 Dépannage

### Problème : Le moniteur ne compte pas les tokens

**Solution** :
- Vérifiez que vous utilisez `TokenMonitoringSummariser` et non `Summariser`
- Assurez-vous d'appeler `summarise_with_token_monitoring()` et non `summarise()`
- Vérifiez que les dépendances sont installées (`atomic_agents`, `litellm`)

### Problème : Les nombres semblent incorrects

**Solution** :
- Vérifiez que vous utilisez le bon modèle
- Assurez-vous que les appels aux agents passent bien par le moniteur
- Comparez avec un appel manuel pour vérifier

### Problème : Performance ralentie

**Solution** :
- Le comptage des tokens ajoute un léger overhead
- Désactivez la surveillance en production si nécessaire
- Utilisez la surveillance uniquement pour le débogage et l'optimisation

## 📚 Référence

### Méthodes Disponibles

- `summarise_with_token_monitoring()` : Résumé avec surveillance
- `print_token_summary()` : Affiche un résumé formaté
- `reset_token_counters()` : Réinitialise les compteurs

### Attributs Accessibles

- `total_input_tokens` : Tokens d'entrée cumulés
- `total_output_tokens` : Tokens de sortie cumulés
- `call_count` : Nombre d'appels aux agents
- `model` : Modèle utilisé

## 🎉 Conclusion

L'intégration du moniteur de tokens dans le processus de résumé est simple et fournit des informations précieuses pour :

- **Optimiser les coûts** en surveillant l'utilisation des tokens
- **Améliorer les performances** en analysant les ratios
- **Déboguer** les problèmes de consommation excessive
- **Comparer** différents modèles et approches

La solution est prête à l'emploi et peut être intégrée progressivement dans votre workflow existant.