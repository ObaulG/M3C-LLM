# Modèle utilisateur, connaissances et observations

## Objectif

Construire un modèle évolutif du visiteur afin d'adapter les contenus, les interactions et les recommandations. Le système ne mesure pas directement l'appropriation : il en estime des **indicateurs observables**, conservés avec leur provenance et leur niveau de confiance.

## 1. Éléments de connaissance

Une ressource documentaire peut contenir plusieurs connaissances atomiques :

```text
Knowledge = {
  id,
  proposition,       // information formulée et vérifiable
  entity_ids[],      // personnes, lieux, œuvres, événements, pratiques…
  theme_ids[],       // thèmes associés
  sources[]          // ressource, extrait/page et URI
}
```

Formellement : `k = (id_k, p_k, E_k, T_k, S_k)`.

- Une **ressource** est le document d'origine ; une **connaissance** est une proposition précise extraite de cette ressource.
- Toute connaissance doit être reliée à au moins une source.
- Les thèmes et entités servent à relier les connaissances, calculer les intérêts et recommander des contenus.

## 2. Observations

Une observation est un événement horodaté et non une conclusion sur le visiteur :

```text
Observation = {
  id, user_id, type, timestamp,
  context,             // session, page, ressource, dispositif
  target_ids[],        // connaissances, thèmes ou entités concernés
  payload,             // donnée brute ou résultat structuré
  confidence           // fiabilité de l'interprétation, de 0 à 1
}
```

Trois familles sont retenues :

| Type | Exemples | Usage principal |
| --- | --- | --- |
| **Déclarative** | langue, objectif de visite, préférence, familiarité déclarée | Paramètres et préférences explicites |
| **Comportementale** | consultation, recherche, clic, temps de lecture, question posée | Estimation prudente des intérêts |
| **Évaluative** | réponse libre, score, éléments corrects/manquants, nouvelle tentative | Estimation de l'état des connaissances |

Les données brutes sont conservées ; toute analyse produite par un LLM est enregistrée comme une interprétation avec le modèle, le prompt et la confiance associés.

## 3. Modèle utilisateur

```text
UserModel = {
  user_id,
  profile: {
    languages[], visit_goal?, detail_level?, accessibility_needs[]
  },
  interests: {
    themes:  [{ id, weight, confidence, evidence_ids[] }],
    entities:[{ id, weight, confidence, evidence_ids[] }]
  },
  knowledge_states: [{
    knowledge_id,
    status,           // unknown | encountered | developing | demonstrated
    score,            // estimation de 0 à 1
    confidence,
    evidence_ids[],
    updated_at
  }],
  updated_at
}
```

Le modèle est **dynamique, explicable et révisable** : chaque valeur dérivée renvoie aux observations qui la justifient.

## 4. Règles minimales de mise à jour

1. Une observation déclarative met à jour le profil ou les préférences ; elle reste modifiable par le visiteur.
2. Une observation comportementale renforce surtout un intérêt. Une consultation seule ne prouve jamais l'acquisition d'une connaissance.
3. Une observation évaluative met à jour l'état des connaissances ; plusieurs observations concordantes augmentent le score et la confiance.
4. Une réponse partielle doit enregistrer les connaissances démontrées et manquantes séparément.
5. Les recommandations ciblent des contenus proches des intérêts, mais peuvent privilégier une connaissance manquante ou en cours d'acquisition.
6. Les informations générées restent reliées aux connaissances et aux sources patrimoniales mobilisées.

## 5. Flux fonctionnel

```text
interaction -> observation -> interprétation -> mise à jour du modèle
            -> sélection d'un contenu ou d'une action de médiation
            -> nouvelle observation
```

À prévoir côté développement : stockage des connaissances et de leurs sources, journal d'observations immuable, projection recalculable du modèle utilisateur, puis service de sélection/recommandation.
