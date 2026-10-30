# 📊 Rapport d'évaluation des réponses

Généré le: 2026-10-30 18:52:40

Fichier CSV source: evaluation_input_template.csv

## 📈 Statistiques globales

- **Nombre de questions évaluées**: 18
- **Nombre de modèles utilisés**: 4
- **Modèles**: mistral:ministral-14b-2512, mistral:ministral-3b-2512, mistral:ministral-8b-2512, mistral:mistral-small-2603

## 🎯 Scores moyens par modèle

| Modèle | Score moyen | Nombre d'évaluations |
|--------|-------------|---------------------|
| mistral:ministral-14b-2512 | 5.89 | 18 |
| mistral:ministral-3b-2512 | 6.00 | 18 |
| mistral:ministral-8b-2512 | 5.83 | 18 |
| mistral:mistral-small-2603 | 5.89 | 18 |

## 🔍 Scores moyens par modèle (évaluation par les faits)

| Modèle | Score moyen (faits) | Nombre d'évaluations |
|--------|--------------------|---------------------|
| mistral:ministral-14b-2512 | 3.69 | 13 |
| mistral:ministral-3b-2512 | 4.71 | 13 |
| mistral:ministral-8b-2512 | 3.17 | 13 |
| mistral:mistral-small-2603 | 3.94 | 13 |

## 📏 Scores moyens par nombre de réponses de référence

| Nb réponses de référence | Score moyen | Nb évaluations |
|--------------------------|-------------|----------------|
| 1 | 5.90 | 72 |

## Question 1: 452

**Texte**: Pourquoi la langue corse présente-t-elle des variations selon les régions ?

**Réponse humaine**: parce que chacun va dire la sienne

**Note attendue**: 7/10

**Temps total**: 12.07s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-3b-2512 | 1 | 2/10 | La réponse de l’utilisateur capture l’idée général... | 6.245 |
| mistral:ministral-8b-2512 | 1 | 2/10 | Ta réponse est trop simplifiée et ne capture pas l... | 4.708 |
| mistral:ministral-14b-2512 | 1 | 2/10 | La réponse proposée ne capture pas la richesse ni ... | 5.188 |
| mistral:mistral-small-2603 | 1 | 2/10 | La réponse évoque une idée de subjectivité ('chacu... | 3.661 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 2.00/10 | 5.00 |

### 🔍 Évaluations par les faits

**Nombre de faits (affirmations) de référence**: 6

| Modèle | Nb faits | Présents | Partiels | Absents | Score | Temps (s) |
|--------|----------|----------|----------|---------|-------|-----------|
| mistral:ministral-8b-2512 | 6 | 0 | 1 | 5 | 0.83/10 | 3.550 |
| mistral:ministral-3b-2512 | 6 | 0 | 0 | 6 | 0.0/10 | 3.301 |
| mistral:ministral-14b-2512 | 6 | 0 | 0 | 6 | 0.0/10 | 4.208 |
| mistral:mistral-small-2603 | 6 | 0 | 0 | 6 | 0.0/10 | 1.981 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 7/10):

- **Modèles**: mistral:ministral-3b-2512
- **Score moyen**: 2.00/10
- **Écart avec la note attendue**: 5.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=2.00, min=2.00, max=2.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=2.00, min=2.00, max=2.00 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=2.00, min=2.00, max=2.00 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=2.00, min=2.00, max=2.00 (toutes tailles de prompt confondues)

## Question 2: 452

**Texte**: Pourquoi la langue corse présente-t-elle des variations selon les régions ?

**Réponse humaine**: Les habitants d’une région veulent pouvoir se distinguer des autres

**Note attendue**: 7/10

**Temps total**: 5.69s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-8b-2512 | 1 | 5/10 | Ta réponse touche au cœur du sujet en évoquant le ... | 1.394 |
| mistral:mistral-small-2603 | 1 | 5/10 | Tu as saisi un aspect important : la volonté de di... | 1.765 |
| mistral:ministral-3b-2512 | 1 | 4/10 | Ta réponse touche sur l’aspect identitaire et de d... | 0.918 |
| mistral:ministral-14b-2512 | 1 | 4/10 | Votre réponse souligne une volonté de distinction,... | 1.961 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 4.50/10 | 2.50 |

### 🔍 Évaluations par les faits

**Nombre de faits (affirmations) de référence**: 6

| Modèle | Nb faits | Présents | Partiels | Absents | Score | Temps (s) |
|--------|----------|----------|----------|---------|-------|-----------|
| mistral:ministral-14b-2512 | 6 | 1 | 2 | 3 | 3.33/10 | 3.701 |
| mistral:ministral-3b-2512 | 6 | 0 | 2 | 4 | 1.67/10 | 1.586 |
| mistral:ministral-8b-2512 | 6 | 1 | 0 | 5 | 1.67/10 | 2.680 |
| mistral:mistral-small-2603 | 6 | 0 | 2 | 4 | 1.67/10 | 2.035 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 7/10):

- **Modèles**: mistral:ministral-8b-2512
- **Score moyen**: 5.00/10
- **Écart avec la note attendue**: 2.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=4.50, min=4.00, max=5.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=4.50, min=4.00, max=5.00 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=4.50, min=4.33, max=4.67 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=4.50, min=4.50, max=4.50 (toutes tailles de prompt confondues)

## Question 3: 452

**Texte**: Pourquoi la langue corse présente-t-elle des variations selon les régions ?

**Réponse humaine**: les variations existent pour que les différents groupes puissent se distinguer

**Note attendue**: 8/10

**Temps total**: 6.13s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-8b-2512 | 1 | 6/10 | Tu as bien identifié l’idée centrale que ces varia... | 1.476 |
| mistral:mistral-small-2603 | 1 | 6/10 | Tu as bien identifié l’idée de distinction entre l... | 0.972 |
| mistral:ministral-3b-2512 | 1 | 5/10 | Ta réponse souligne bien l’idée de distinction ent... | 0.899 |
| mistral:ministral-14b-2512 | 1 | 5/10 | Vous touchez là à une réalité importante : ces var... | 2.425 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 5.50/10 | 2.50 |

### 🔍 Évaluations par les faits

**Nombre de faits (affirmations) de référence**: 6

| Modèle | Nb faits | Présents | Partiels | Absents | Score | Temps (s) |
|--------|----------|----------|----------|---------|-------|-----------|
| mistral:ministral-3b-2512 | 6 | 2 | 1 | 3 | 4.17/10 | 3.655 |
| mistral:ministral-14b-2512 | 6 | 1 | 2 | 3 | 3.33/10 | 3.491 |
| mistral:ministral-8b-2512 | 6 | 0 | 2 | 4 | 1.67/10 | 2.329 |
| mistral:mistral-small-2603 | 6 | 0 | 2 | 4 | 1.67/10 | 1.880 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 8/10):

- **Modèles**: mistral:ministral-8b-2512
- **Score moyen**: 6.00/10
- **Écart avec la note attendue**: 2.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=5.50, min=5.00, max=6.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=5.50, min=5.00, max=6.00 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=5.50, min=5.33, max=5.67 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=5.50, min=5.50, max=5.50 (toutes tailles de prompt confondues)

## Question 4: 675

**Texte**: Quelle est la différence entre les formes « s’hè » et « s’è » en corse ?

**Réponse humaine**: « s’hè » c’est le verbe « esse »

**Note attendue**: 4/10

**Temps total**: 2.06s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-8b-2512 | 1 | 4/10 | Ta réponse est partielle, car elle ne distingue pa... | 1.197 |
| mistral:mistral-small-2603 | 1 | 4/10 | Tu as identifié correctement que « s’hè » est lié ... | 1.455 |
| mistral:ministral-3b-2512 | 1 | 3/10 | Ta réponse identifie correctement que « s’hè » est... | 0.990 |
| mistral:ministral-14b-2512 | 1 | 3/10 | Vous mentionnez correctement que *« s’hè »* est li... | 2.036 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 3.50/10 | 0.50 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 4/10):

- **Modèles**: mistral:ministral-8b-2512
- **Score moyen**: 4.00/10
- **Écart avec la note attendue**: 0.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=3.50, min=3.00, max=4.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=3.50, min=3.00, max=4.00 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=3.50, min=3.33, max=3.67 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=3.50, min=3.50, max=3.50 (toutes tailles de prompt confondues)

## Question 5: 675

**Texte**: Quelle est la différence entre les formes « s’hè » et « s’è » en corse ?

**Réponse humaine**: « s’hè » est la forme réfléchie de « esse », et « s’è » est la contraction de « si », et « è »

**Note attendue**: 7/10

**Temps total**: 2.13s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-8b-2512 | 1 | 8/10 | Ta réponse est déjà très claire et précise sur l’e... | 1.102 |
| mistral:ministral-3b-2512 | 1 | 7/10 | Ta réponse aborde les deux éléments clés de la dis... | 1.023 |
| mistral:ministral-14b-2512 | 1 | 7/10 | Votre réponse capture bien l’essentiel des différe... | 2.100 |
| mistral:mistral-small-2603 | 1 | 5/10 | Presque ! Tu as bien noté que « s’hè » est lié à l... | 1.166 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 6.75/10 | 0.25 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 7/10):

- **Modèles**: mistral:ministral-3b-2512
- **Score moyen**: 7.00/10
- **Écart avec la note attendue**: 0.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=6.75, min=5.00, max=8.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=6.75, min=6.00, max=7.50 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=6.75, min=6.33, max=7.33 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=6.75, min=6.75, max=6.75 (toutes tailles de prompt confondues)

## Question 6: 2534

**Texte**: Quels exemples concrets sont donnés dans le texte pour illustrer l'idée que la consommation culturelle remplace partiellement le rôle de la langue dans l'identité corse ?

**Réponse humaine**: si quelqu un mange corse, alors il est corse

**Note attendue**: 3/10

**Temps total**: 5.72s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-3b-2512 | 1 | 3/10 | Ta réponse réduit l’idée à une simple action culin... | 0.817 |
| mistral:ministral-8b-2512 | 1 | 3/10 | Ta réponse résume une idée partielle du phénomène,... | 1.350 |
| mistral:mistral-small-2603 | 1 | 3/10 | La réponse est trop vague et ne reflète pas les ex... | 1.103 |
| mistral:ministral-14b-2512 | 1 | 2/10 | Votre réponse simplifie excessivement une notion c... | 2.173 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 2.75/10 | 0.25 |

### 🔍 Évaluations par les faits

**Nombre de faits (affirmations) de référence**: 6

| Modèle | Nb faits | Présents | Partiels | Absents | Score | Temps (s) |
|--------|----------|----------|----------|---------|-------|-----------|
| mistral:ministral-3b-2512 | 6 | 0 | 2 | 4 | 1.88/10 | 2.441 |
| mistral:ministral-8b-2512 | 6 | 0 | 1 | 5 | 0.94/10 | 2.153 |
| mistral:ministral-14b-2512 | 6 | 0 | 0 | 6 | 0.0/10 | 3.526 |
| mistral:mistral-small-2603 | 6 | 0 | 0 | 6 | 0.0/10 | 1.951 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 3/10):

- **Modèles**: mistral:ministral-3b-2512
- **Score moyen**: 3.00/10
- **Écart avec la note attendue**: 0.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=2.75, min=2.00, max=3.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=2.75, min=2.50, max=3.00 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=2.75, min=2.67, max=3.00 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=2.75, min=2.75, max=2.75 (toutes tailles de prompt confondues)

## Question 7: 2534

**Texte**: Quels exemples concrets sont donnés dans le texte pour illustrer l'idée que la consommation culturelle remplace partiellement le rôle de la langue dans l'identité corse ?

**Réponse humaine**: Autrement que la maîtrise de la langue, manger local, acheter les vêtements ici, supporter le Sporting sont autant de moyens de se considérer Corse

**Note attendue**: 7/10

**Temps total**: 7.55s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-3b-2512 | 1 | 8/10 | Ta réponse couvre de manière pertinente et large l... | 0.843 |
| mistral:ministral-14b-2512 | 1 | 8/10 | Votre réponse illustre parfaitement les mécanismes... | 2.435 |
| mistral:mistral-small-2603 | 1 | 8/10 | Tu as bien cerné plusieurs éléments clés : la gast... | 1.257 |
| mistral:ministral-8b-2512 | 1 | 7/10 | Ta réponse capture bien l’idée que la consommation... | 1.327 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 7.75/10 | 0.75 |

### 🔍 Évaluations par les faits

**Nombre de faits (affirmations) de référence**: 6

| Modèle | Nb faits | Présents | Partiels | Absents | Score | Temps (s) |
|--------|----------|----------|----------|---------|-------|-----------|
| mistral:ministral-3b-2512 | 6 | 5 | 0 | 1 | 9.38/10 | 2.022 |
| mistral:ministral-14b-2512 | 6 | 3 | 2 | 1 | 7.5/10 | 5.097 |
| mistral:mistral-small-2603 | 6 | 3 | 1 | 2 | 6.56/10 | 2.200 |
| mistral:ministral-8b-2512 | 6 | 2 | 2 | 2 | 5.62/10 | 2.333 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 7/10):

- **Modèles**: mistral:ministral-8b-2512
- **Score moyen**: 7.00/10
- **Écart avec la note attendue**: 0.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=7.75, min=7.00, max=8.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=7.75, min=7.50, max=8.00 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=7.75, min=7.67, max=8.00 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=7.75, min=7.75, max=7.75 (toutes tailles de prompt confondues)

## Question 8: 2534

**Texte**: Quels exemples concrets sont donnés dans le texte pour illustrer l'idée que la consommation culturelle remplace partiellement le rôle de la langue dans l'identité corse ?

**Réponse humaine**: La consommation culturelle, comme par exemple la gastronomie, la mode, les cosmétiques, et le Sporting, est un élément qui permet de revendiquer une appartenance à la Corse, même sans maîtriser sa langue.

**Note attendue**: 9/10

**Temps total**: 7.54s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-3b-2512 | 1 | 9/10 | Ta réponse est très proche des attentes et couvre ... | 0.997 |
| mistral:ministral-14b-2512 | 1 | 9/10 | Votre réponse est très précise et couvre l’essenti... | 2.781 |
| mistral:mistral-small-2603 | 1 | 9/10 | Excellent ! Ta réponse couvre presque tous les exe... | 1.260 |
| mistral:ministral-8b-2512 | 1 | 8/10 | Ta réponse est claire et synthétique, et tu as bie... | 4.013 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 8.75/10 | 0.25 |

### 🔍 Évaluations par les faits

**Nombre de faits (affirmations) de référence**: 6

| Modèle | Nb faits | Présents | Partiels | Absents | Score | Temps (s) |
|--------|----------|----------|----------|---------|-------|-----------|
| mistral:ministral-3b-2512 | 6 | 4 | 1 | 1 | 8.44/10 | 2.001 |
| mistral:ministral-14b-2512 | 6 | 3 | 0 | 3 | 5.62/10 | 3.505 |
| mistral:mistral-small-2603 | 6 | 2 | 2 | 2 | 5.62/10 | 1.656 |
| mistral:ministral-8b-2512 | 6 | 2 | 1 | 3 | 4.69/10 | 2.318 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 9/10):

- **Modèles**: mistral:ministral-3b-2512
- **Score moyen**: 9.00/10
- **Écart avec la note attendue**: 0.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=8.75, min=8.00, max=9.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=8.75, min=8.50, max=9.00 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=8.75, min=8.67, max=9.00 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=8.75, min=8.75, max=8.75 (toutes tailles de prompt confondues)

## Question 9: 2535

**Texte**: Pourquoi le football est-il considéré comme un vecteur puissant d'identification en Corse, selon le texte ?

**Réponse humaine**: Le football est l’un des plus puissants vecteurs d’identification culturel pour s’identifier à une ville ou une région, et encore plus pour les clubs locaux, comme celui du Sporting

**Note attendue**: 7/10

**Temps total**: 7.71s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-3b-2512 | 1 | 8/10 | Ta réponse capture l’essentiel de la puissance ide... | 0.886 |
| mistral:mistral-small-2603 | 1 | 8/10 | Ta réponse est très pertinente et couvre l'essenti... | 0.993 |
| mistral:ministral-14b-2512 | 1 | 7/10 | Votre réponse met bien en avant le rôle central du... | 3.332 |
| mistral:ministral-8b-2512 | 1 | 6/10 | Tu as bien saisi que le football, notamment à trav... | 1.135 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 7.25/10 | 0.25 |

### 🔍 Évaluations par les faits

**Nombre de faits (affirmations) de référence**: 6

| Modèle | Nb faits | Présents | Partiels | Absents | Score | Temps (s) |
|--------|----------|----------|----------|---------|-------|-----------|
| mistral:ministral-3b-2512 | 6 | 5 | 0 | 1 | 9.29/10 | 4.368 |
| mistral:ministral-14b-2512 | 6 | 3 | 1 | 2 | 6.79/10 | 3.119 |
| mistral:mistral-small-2603 | 6 | 3 | 1 | 2 | 6.79/10 | 1.814 |
| mistral:ministral-8b-2512 | 6 | 1 | 1 | 4 | 3.21/10 | 1.908 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 7/10):

- **Modèles**: mistral:ministral-14b-2512
- **Score moyen**: 7.00/10
- **Écart avec la note attendue**: 0.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=7.25, min=6.00, max=8.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=7.25, min=6.50, max=8.00 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=7.25, min=7.00, max=7.67 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=7.25, min=7.25, max=7.25 (toutes tailles de prompt confondues)

## Question 10: 417

**Texte**: Question 417

**Réponse humaine**: Teghime coupe symboliquement la méditérranée en deux mers, d'est en ouest. Il est un lieu symbolique de la question de l'écologie, avec la décharge publique de Bastia

**Note attendue**: 7/10

**Temps total**: 3.72s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-3b-2512 | 1 | 6/10 | Ta réponse mentionne correctement que le col de Te... | 2.675 |
| mistral:ministral-8b-2512 | 1 | 5/10 | Ta réponse touche à deux aspects intéressants : la... | 1.403 |
| mistral:ministral-14b-2512 | 1 | 5/10 | Vous avez bien saisi l’aspect symbolique du col de... | 3.672 |
| mistral:mistral-small-2603 | 1 | 4/10 | Ta réponse évoque bien la division symbolique de l... | 1.138 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 5.00/10 | 2.00 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 7/10):

- **Modèles**: mistral:ministral-3b-2512
- **Score moyen**: 6.00/10
- **Écart avec la note attendue**: 1.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=5.00, min=4.00, max=6.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=5.00, min=4.50, max=5.50 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=5.00, min=4.67, max=5.33 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=5.00, min=5.00, max=5.00 (toutes tailles de prompt confondues)

## Question 11: 417

**Texte**: Question 417

**Réponse humaine**: Teghime permet d’avoir une vue imprenable sur les deux mers, la Méditerranée étant symboliquement coupée en deux, formant la mer Tyrrhénienne

**Note attendue**: 8/10

**Temps total**: 2.27s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-14b-2512 | 1 | 10/10 | Votre réponse est **exacte, précise et fidèle** à ... | 2.254 |
| mistral:ministral-3b-2512 | 1 | 9/10 | Ta réponse est très proche des attentes et capture... | 1.182 |
| mistral:ministral-8b-2512 | 1 | 9/10 | Ta réponse est très précise et capture parfaitemen... | 1.238 |
| mistral:mistral-small-2603 | 1 | 9/10 | Parfait ! Ta réponse capture exactement l'essentie... | 0.860 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 9.25/10 | 1.25 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 8/10):

- **Modèles**: mistral:ministral-3b-2512
- **Score moyen**: 9.00/10
- **Écart avec la note attendue**: 1.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=9.25, min=9.00, max=10.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=9.25, min=9.00, max=9.50 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=9.25, min=9.00, max=9.33 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=9.25, min=9.25, max=9.25 (toutes tailles de prompt confondues)

## Question 12: 417

**Texte**: Question 417

**Réponse humaine**: Teghime coupe symboliquement la mer Méditérranée en deux

**Note attendue**: 5/10

**Temps total**: 18.84s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-3b-2512 | 1 | 7/10 | Ta réponse aborde correctement l’idée centrale que... | 0.846 |
| mistral:ministral-8b-2512 | 1 | 6/10 | Tu as identifié l’idée principale : le col de Tegh... | 18.816 |
| mistral:ministral-14b-2512 | 1 | 6/10 | Vous avez saisi l’essence symbolique du col de Teg... | 1.789 |
| mistral:mistral-small-2603 | 1 | 6/10 | Tu as saisi l'idée principale de la division symbo... | 1.122 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 6.25/10 | 1.25 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 5/10):

- **Modèles**: mistral:ministral-8b-2512
- **Score moyen**: 6.00/10
- **Écart avec la note attendue**: 1.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=6.25, min=6.00, max=7.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=6.25, min=6.00, max=6.50 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=6.25, min=6.00, max=6.33 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=6.25, min=6.25, max=6.25 (toutes tailles de prompt confondues)

## Question 13: 129

**Texte**: Quel rôle historique a joué le couvent d'Alisgiani dans la Révolution corse ?

**Réponse humaine**: L’indépendance de la Corse

**Note attendue**: 4/10

**Temps total**: 6.06s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-3b-2512 | 1 | 3/10 | Ta réponse est trop succincte et ne précise pas le... | 1.654 |
| mistral:ministral-8b-2512 | 1 | 3/10 | Ta réponse mentionne un résultat important, mais e... | 1.289 |
| mistral:ministral-14b-2512 | 1 | 3/10 | Votre réponse évoque bien l’idée centrale liée à l... | 2.474 |
| mistral:mistral-small-2603 | 1 | 3/10 | Ta réponse est trop vague et ne mentionne aucun de... | 1.157 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 3.00/10 | 1.00 |

### 🔍 Évaluations par les faits

**Nombre de faits (affirmations) de référence**: 5

| Modèle | Nb faits | Présents | Partiels | Absents | Score | Temps (s) |
|--------|----------|----------|----------|---------|-------|-----------|
| mistral:ministral-8b-2512 | 5 | 0 | 1 | 4 | 1.15/10 | 1.890 |
| mistral:ministral-3b-2512 | 5 | 0 | 0 | 5 | 0.0/10 | 1.626 |
| mistral:ministral-14b-2512 | 5 | 0 | 0 | 5 | 0.0/10 | 3.565 |
| mistral:mistral-small-2603 | 5 | 0 | 0 | 5 | 0.0/10 | 1.583 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 4/10):

- **Modèles**: mistral:ministral-3b-2512
- **Score moyen**: 3.00/10
- **Écart avec la note attendue**: 1.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=3.00, min=3.00, max=3.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=3.00, min=3.00, max=3.00 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=3.00, min=3.00, max=3.00 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=3.00, min=3.00, max=3.00 (toutes tailles de prompt confondues)

## Question 14: 129

**Texte**: Quel rôle historique a joué le couvent d'Alisgiani dans la Révolution corse ?

**Réponse humaine**: C’est un symbole de liberté pendant la Révolution corse

**Note attendue**: 6/10

**Temps total**: 5.81s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-3b-2512 | 1 | 5/10 | Ta réponse identifie bien l’aspect symbolique de l... | 0.890 |
| mistral:ministral-8b-2512 | 1 | 5/10 | Ton réponse évoque bien l’aspect symbolique de lib... | 0.920 |
| mistral:ministral-14b-2512 | 1 | 5/10 | Vous touchez bien à l’aspect **symbolique fort** d... | 2.796 |
| mistral:mistral-small-2603 | 1 | 5/10 | Tu as saisi l'idée de liberté, mais la réponse res... | 1.070 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 5.00/10 | 1.00 |

### 🔍 Évaluations par les faits

**Nombre de faits (affirmations) de référence**: 5

| Modèle | Nb faits | Présents | Partiels | Absents | Score | Temps (s) |
|--------|----------|----------|----------|---------|-------|-----------|
| mistral:ministral-3b-2512 | 5 | 1 | 1 | 3 | 1.92/10 | 1.564 |
| mistral:ministral-8b-2512 | 5 | 0 | 1 | 4 | 0.38/10 | 2.643 |
| mistral:ministral-14b-2512 | 5 | 0 | 1 | 4 | 0.38/10 | 2.966 |
| mistral:mistral-small-2603 | 5 | 0 | 1 | 4 | 0.38/10 | 1.625 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 6/10):

- **Modèles**: mistral:ministral-3b-2512
- **Score moyen**: 5.00/10
- **Écart avec la note attendue**: 1.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=5.00, min=5.00, max=5.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=5.00, min=5.00, max=5.00 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=5.00, min=5.00, max=5.00 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=5.00, min=5.00, max=5.00 (toutes tailles de prompt confondues)

## Question 15: 484

**Texte**: Comment le système orthographique corse transcrit-il l'opposition entre consonnes sourdes et sonores ?

**Réponse humaine**: Les sons forts sont représentés en doublant la consonne, les sons plus faibles avec une consonne simple.

**Note attendue**: 7/10

**Temps total**: 5.10s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-14b-2512 | 1 | 9/10 | Votre réponse est **claire et fidèle** à la logiqu... | 2.444 |
| mistral:mistral-small-2603 | 1 | 8/10 | Ta réponse est très proche de la formulation atten... | 0.980 |
| mistral:ministral-3b-2512 | 1 | 7/10 | Ta réponse capture l’idée générale de la règle ort... | 0.891 |
| mistral:ministral-8b-2512 | 1 | 7/10 | Ta réponse résume bien le principe général de l’op... | 1.113 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 7.75/10 | 0.75 |

### 🔍 Évaluations par les faits

**Nombre de faits (affirmations) de référence**: 4

| Modèle | Nb faits | Présents | Partiels | Absents | Score | Temps (s) |
|--------|----------|----------|----------|---------|-------|-----------|
| mistral:ministral-3b-2512 | 4 | 2 | 0 | 2 | 7.5/10 | 1.405 |
| mistral:ministral-14b-2512 | 4 | 2 | 0 | 2 | 7.5/10 | 2.632 |
| mistral:mistral-small-2603 | 4 | 2 | 0 | 2 | 7.5/10 | 1.235 |
| mistral:ministral-8b-2512 | 4 | 0 | 2 | 2 | 3.75/10 | 1.844 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 7/10):

- **Modèles**: mistral:ministral-3b-2512
- **Score moyen**: 7.00/10
- **Écart avec la note attendue**: 0.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=7.75, min=7.00, max=9.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=7.75, min=7.00, max=8.50 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=7.75, min=7.33, max=8.00 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=7.75, min=7.75, max=7.75 (toutes tailles de prompt confondues)

## Question 16: 533

**Texte**: Quels sont les termes utilisés pour exprimer « beaucoup » dans les différents régiolectes corses ?

**Réponse humaine**: "monda" et "assai"

**Note attendue**: 4/10

**Temps total**: 5.14s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-3b-2512 | 1 | 6/10 | Ta réponse mentionne correctement deux termes clés... | 1.118 |
| mistral:ministral-8b-2512 | 1 | 6/10 | Tu as identifié deux termes majeurs, « monda » et ... | 1.505 |
| mistral:ministral-14b-2512 | 1 | 6/10 | Vous avez correctement identifié deux termes majeu... | 2.426 |
| mistral:mistral-small-2603 | 1 | 6/10 | Ta réponse identifie correctement deux termes impo... | 1.025 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 6.00/10 | 2.00 |

### 🔍 Évaluations par les faits

**Nombre de faits (affirmations) de référence**: 4

| Modèle | Nb faits | Présents | Partiels | Absents | Score | Temps (s) |
|--------|----------|----------|----------|---------|-------|-----------|
| mistral:ministral-3b-2512 | 4 | 2 | 0 | 2 | 7.5/10 | 1.140 |
| mistral:mistral-small-2603 | 4 | 2 | 0 | 2 | 7.5/10 | 1.775 |
| mistral:ministral-8b-2512 | 4 | 0 | 2 | 2 | 3.75/10 | 1.801 |
| mistral:ministral-14b-2512 | 4 | 0 | 0 | 4 | 0.0/10 | 2.688 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 4/10):

- **Modèles**: mistral:ministral-3b-2512
- **Score moyen**: 6.00/10
- **Écart avec la note attendue**: 2.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=6.00, min=6.00, max=6.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=6.00, min=6.00, max=6.00 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=6.00, min=6.00, max=6.00 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=6.00, min=6.00, max=6.00 (toutes tailles de prompt confondues)

## Question 17: 533

**Texte**: Quels sont les termes utilisés pour exprimer « beaucoup » dans les différents régiolectes corses ?

**Réponse humaine**: "monda" pour le registre méridional, "assai" pour le registre septentrional

**Note attendue**: 8/10

**Temps total**: 4.60s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-3b-2512 | 1 | 8/10 | Ta réponse couvre les deux registres principaux («... | 1.093 |
| mistral:ministral-8b-2512 | 1 | 8/10 | Ta réponse est précise et bien ciblée, en distingu... | 1.146 |
| mistral:ministral-14b-2512 | 1 | 8/10 | Votre réponse est **très précise** et couvre parfa... | 2.229 |
| mistral:mistral-small-2603 | 1 | 7/10 | Ta réponse est presque complète et bien structurée... | 1.008 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 7.75/10 | 0.25 |

### 🔍 Évaluations par les faits

**Nombre de faits (affirmations) de référence**: 4

| Modèle | Nb faits | Présents | Partiels | Absents | Score | Temps (s) |
|--------|----------|----------|----------|---------|-------|-----------|
| mistral:ministral-3b-2512 | 4 | 2 | 0 | 2 | 7.5/10 | 1.429 |
| mistral:ministral-8b-2512 | 4 | 2 | 0 | 2 | 7.5/10 | 1.621 |
| mistral:ministral-14b-2512 | 4 | 2 | 0 | 2 | 7.5/10 | 2.336 |
| mistral:mistral-small-2603 | 4 | 2 | 0 | 2 | 7.5/10 | 1.227 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 8/10):

- **Modèles**: mistral:ministral-3b-2512
- **Score moyen**: 8.00/10
- **Écart avec la note attendue**: 0.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=7.75, min=7.00, max=8.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=7.75, min=7.50, max=8.00 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=7.75, min=7.67, max=8.00 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=7.75, min=7.75, max=7.75 (toutes tailles de prompt confondues)

## Question 18: 535

**Texte**: Quels sont les termes utilisés pour désigner un « fou » dans les différents dialectes corses ?

**Réponse humaine**: on a "scemu", "scioccu", ou "pazzu" par exemple

**Note attendue**: 7/10

**Temps total**: 5.18s

### 🔍 Évaluations individuelles

| Modèle | Nb réponses réf. | Score | Feedback | Temps (s) |
|--------|-----------------|-------|---------|-----------|
| mistral:ministral-3b-2512 | 1 | 8/10 | Ta réponse inclut trois termes majeurs (*scemu*, *... | 0.764 |
| mistral:mistral-small-2603 | 1 | 8/10 | Ta réponse est très pertinente et couvre bien les ... | 0.855 |
| mistral:ministral-8b-2512 | 1 | 7/10 | Ta réponse mentionne correctement plusieurs termes... | 1.082 |
| mistral:ministral-14b-2512 | 1 | 7/10 | Vous avez tout à fait raison de mentionner *« scem... | 2.566 |

### 📏 Impact du nombre de réponses de référence

| Nb réponses réf. | Score moyen (tous modèles) | Écart avec note attendue |
|-----------------|-----------------------------|--------------------------|
| 1 | 7.50/10 | 0.50 |

### 🔍 Évaluations par les faits

**Nombre de faits (affirmations) de référence**: 5

| Modèle | Nb faits | Présents | Partiels | Absents | Score | Temps (s) |
|--------|----------|----------|----------|---------|-------|-----------|
| mistral:ministral-8b-2512 | 5 | 3 | 0 | 2 | 6.0/10 | 2.114 |
| mistral:ministral-14b-2512 | 5 | 3 | 0 | 2 | 6.0/10 | 2.585 |
| mistral:mistral-small-2603 | 5 | 3 | 0 | 2 | 6.0/10 | 1.367 |
| mistral:ministral-3b-2512 | 5 | 1 | 0 | 4 | 2.0/10 | 1.231 |

### 🏆 Meilleure combinaison (la plus proche de la note attendue 7/10):

- **Modèles**: mistral:ministral-8b-2512
- **Score moyen**: 7.00/10
- **Écart avec la note attendue**: 0.00

### 📊 Moyennes par taille de combinaison

- **1 modèle(s)**: moyenne=7.50, min=7.00, max=8.00 (toutes tailles de prompt confondues)
- **2 modèle(s)**: moyenne=7.50, min=7.00, max=8.00 (toutes tailles de prompt confondues)
- **3 modèle(s)**: moyenne=7.50, min=7.33, max=7.67 (toutes tailles de prompt confondues)
- **4 modèle(s)**: moyenne=7.50, min=7.50, max=7.50 (toutes tailles de prompt confondues)

## 🎉 Analyse finale

- **Score moyen global**: 5.90/10

---
Rapport généré par QuestionAnswerEvaluator | 2026-10-30 18:52:40
