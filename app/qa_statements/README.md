# qa_statements : représentation questions-réponses par affirmations

Prototype isolé de la question-session existante. Ici, une réponse de référence
n'est plus comparée en bloc à la réponse du visiteur : elle est décomposée en une
liste d'affirmations (propositions) qui la constituent. L'évaluation vérifie
ensuite, pour chaque affirmation, si elle est présente dans la réponse rédigée
par le visiteur.

Tout est contenu dans ce dossier : aucun lien avec l'architecture applicative
existante (routers, sessions, templates), à l'exception des fonctions de lecture
de la base de données (`app.database.database`) et de la fabrique de clients LLM
(`app.agents.instructor_factory`).

## Structure du dossier

| Fichier | Rôle |
|---------|------|
| `qa_statements.json` | Données : pour chaque document, les questions/réponses sélectionnées, chaque réponse étant accompagnée de la liste de ses affirmations |
| `build_dataset.py` | Pioche n questions/réponses existantes pour k documents dans la base, génère les affirmations de chaque réponse via un LLM, et les insère dans `qa_statements.json` |
| `export_answers_csv.py` | Écrit un CSV `question_id,visitor_answer` (une ligne par réponse de visiteur, plusieurs questions) destiné à l'évaluation |
| `evaluate_statements.py` | Pour chaque ligne du CSV, vérifie si chaque affirmation de la réponse de référence est présente dans la réponse du visiteur, puis produit un score de complétude, une validité et un feedback séparé (ton) |

## Format de `qa_statements.json`

```json
{
  "metadata": {
    "created_at": "2026-09-22T10:00:00",
    "updated_at": "2026-09-22T10:00:00",
    "statement_extraction_model": "mistral-medium"
  },
  "documents": {
    "21": {
      "questions": [
        {
          "question_id": 418,
          "question_text": "...",
          "answers": [
            {
              "answer_id": 1234,
              "is_correct": true,
              "content": "...",
              "statements": {
                "necessary": ["affirmation nécessaire 1"],
                "optional": ["complément facultatif 1"],
                "errors": ["erreur ou contradiction 1"]
              }
            }
          ]
        }
      ]
    }
  }
}
```

## Format du CSV de réponses visiteur

Colonnes : `question_id,visitor_answer`. Une ligne par réponse de visiteur,
plusieurs questions possibles. Exemple : `answers_input_template.csv`.

## Barème à trois catégories

Pour chaque question, les affirmations des réponses de référence correctes sont
classées en trois catégories :

| Catégorie JSON | Fonction | Effet sur l'évaluation |
|----------------|----------|------------------------|
| `necessary` | Affirmations nécessaires : leur expression permet de satisfaire la demande | Seules elles comptent dans le score de complétude ; reformulations et informations déjà fournies par la question sont acceptées |
| `optional` | Compléments facultatifs : ils enrichissent la réponse | Signalés s'ils sont présents, mais leur absence ne réduit pas le résultat |
| `errors` | Erreurs ou contradictions pertinentes | Leur présence dans la réponse du visiteur remet en cause sa validité |

## Évaluation

Pour chaque réponse visiteur, le script `evaluate_statements.py` regroupe les
affirmations des réponses de référence correctes de la question, puis :

1. vérifie chaque affirmation nécessaire (présente ? + justification), en
   acceptant les reformulations et les informations déjà fournies par l'énoncé
   de la question ;
2. signale les compléments facultatifs retrouvés (hors score) ;
3. détecte les erreurs ou contradictions pertinentes dans la réponse du
   visiteur ;
4. calcule un **score de complétude** (proportion d'affirmations nécessaires
   retrouvées) et une **validité** (remise en cause si une erreur pertinente est
   détectée) ;
5. rédige un **feedback séparé** qui ne porte que sur la complétude, avec un ton
   contrôlé : il ne doit exiger aucun détail facultatif, ne pas demander de
   répéter le contexte de la question, et rester constructif. Le LLM
   auto-évalue aussi le ton de son propre commentaire (`tone_appropriate`,
   `tone_comment`), afin de distinguer complétude et dureté du feedback.

Les résultats sont écrits dans `results/` (JSON + CSV + rapport Markdown).

## Utilisation

Depuis la racine du dépôt :

```bash
# 1. Constituer le jeu de données : 3 questions pour chacun des documents 21 et 34
python -m app.qa_statements.build_dataset --documents 21 34 --num-questions 3

# 2. Exporter le CSV à remplir avec les réponses du visiteur
python -m app.qa_statements.export_answers_csv --output answers_input_template.csv

# 3. Remplir la colonne visitor_answer puis évaluer
python -m app.qa_statements.evaluate_statements --input answers_input_template.csv
```

Variables d'environnement requises : celles de la base de données MySQL et
`MISTRAL_API_KEY` (ou un serveur Ollama local si `--provider ollama`).
