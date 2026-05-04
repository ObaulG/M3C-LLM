
# Rapport d'évaluation des sessions de médiation

## Résumé des configurations testées

### Modèles ministral

**Meilleure configuration**: 1 eval(ministral-8b-latest)
- Score moyen: 1.2
- Temps total: 3.73s
- Tokens totaux: 3913
- Efficacité (score/temps): 0.34 score/s

| Configuration | Score moyen | Temps (s) | Tokens | Efficacité (score/s) |
|---------------|-------------|-----------|--------|---------------------|
| 1 eval(ministral-8b-latest) | 1.2 | 3.73 | 3913 | 0.335 |
| 3 eval(ministral-3b-latest, ministral-3b-latest, ministral-3b-latest) + final(ministral-3b-latest) | 1.2 | 9.28 | 18845 | 0.135 |
| 1 eval(ministral-3b-latest) | 1.2 | 9.85 | 4472 | 0.127 |

### Modèles mistral

**Meilleure configuration**: 1 eval(mistral-medium)
- Score moyen: 1.0
- Temps total: 7.77s
- Tokens totaux: 4113
- Efficacité (score/temps): 0.13 score/s

| Configuration | Score moyen | Temps (s) | Tokens | Efficacité (score/s) |
|---------------|-------------|-----------|--------|---------------------|
| 1 eval(mistral-medium) | 1.0 | 7.77 | 4113 | 0.129 |
| 1 eval(mistral-large-latest) | 1.2 | 21.15 | 4259 | 0.059 |

## Analyse des temps d'exécution par modèle

| Modèle | Temps moyen (s) | Temps min (s) | Temps max (s) | Écart-type |
|--------|-----------------|---------------|---------------|------------|
| final_ministral-3b-latest | 3.486 | 3.486 | 3.486 | 0.000 |
| ministral-3b-latest | 7.458 | 6.669 | 8.246 | 0.788 |
| ministral-8b-latest | 2.359 | 2.359 | 2.359 | 0.000 |
| mistral-large-latest | 19.977 | 19.977 | 19.977 | 0.000 |
| mistral-medium | 6.552 | 6.552 | 6.552 | 0.000 |

## Analyse globale
- Score moyen global: 1.2
- Temps moyen: 10.36s
- Tokens moyens: 7120
- Meilleure configuration globale: 1 eval(ministral-8b-latest)
  - Score: 1.2
  - Temps: 3.73s
  - Efficacité: 0.335 score/s
