# Module Profile - Page de Profil Utilisateur

Ce module implémente la page de profil utilisateur pour le projet LLMAgents. Il permet d'afficher les statistiques de visite, les ressources consultées, les thèmes explorés et les éléments de connaissance pour chaque utilisateur.

## Structure

```
app/profile/
├── __init__.py              # Module vide
├── models.py               # Modèles Pydantic pour les données du profil
├── router.py               # Endpoints FastAPI pour le profil
├── services.py             # Services de récupération des données
└── page_builder.py         # Construction de la page HTML

app/database/
└── user_profile_views.sql  # Vues SQL pour agréger les données du profil

app/static/
├── profile.html            # Page de profil statique (rendu client via /profile/api/me)
└── auth.html               # Connexion/inscription (redirige vers profile.html si authentifié)

app/templates/
├── pages/
│   └── profile.j2          # Template principal de la page de profil
└── macros/
    ├── knowledge_item_card.html  # Carte pour afficher un élément de connaissance
    ├── resource_card.html       # Carte pour une ressource consultée
    └── theme_stats.html         # Carte pour les statistiques d'un thème
```

## Fonctionnalités

### Page principale (`/profile`)
- **Statistiques globales** : Nombre total d'observations, vues de ressources, vues de thèmes, évaluations
- **Statistiques de connaissance** : Répartition des connaissances par statut (maîtrisées, en développement, rencontrées, inconnues) avec barres de progression
- **Ressources consultées** : Liste des documents/livres consultés avec métadonnées (titre, auteur, date, nombre de consultations)
- **Thèmes explorés** : Cartes avec statistiques par thème (poids d'intérêt, confiance, nombre d'observations, connaissances associées)
- **Éléments de connaissance** : Liste complète des connaissances groupées par thème, avec statut et score
- **Observations** : État des observations conformément au modèle `modele-utilisateur-connaissances-observations.md` — compteurs par famille (déclarative, comportementale, évaluative) et historique des observations récentes avec type spécifique, cibles (connaissances, thèmes, entités), contexte et confiance
- **Compétences** : Section toujours visible sur le profil (page Jinja et page statique) ; elle annonce le suivi des compétences même si aucune observation de compétence n'existe encore, et affichera les compétences observées (nom, niveau estimé, confiance) dès que la donnée sera disponible via le champ `skills` de l'API
- **Export CSV** : Option pour exporter toutes les données du profil (inclut les observations)

### Endpoints API

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/profile/` | GET | Affiche la page de profil (rendu Jinja2) |
| `/profile/api/{user_id}` | GET | Retourne toutes les données du profil en JSON |
| `/profile/api/{user_id}/stats` | GET | Retourne uniquement les statistiques globales |
| `/profile/api/{user_id}/resources` | GET | Retourne la liste des ressources consultées |
| `/profile/api/{user_id}/themes` | GET | Retourne les statistiques par thème |
| `/profile/api/{user_id}/knowledge` | GET | Retourne les éléments de connaissance groupés par thème |
| `/profile/api/{user_id}/observations` | GET | Retourne l'état des observations : compteurs par famille et observations récentes |
| `/profile/api/{user_id}/export/csv` | GET | Télécharge les données du profil en CSV |
| `/profile/api/me` | GET | Retourne les données du profil de l'utilisateur connecté (cookie `m3c_api_key`) |

### Page statique `profile.html`

La page `app/static/profile.html` (servie sur `/static/profile.html`) affiche le profil directement dans le navigateur :

- Même en-tête et navigation que les autres pages du portail (m3c-chatbot.html, etc.), avec le widget de connexion
- Au chargement, elle interroge `GET /profile/api/me` et affiche : statistiques globales, état des observations (compteurs par famille + historique récent), éléments de connaissance par thème
- Si l'utilisateur n'est pas connecté : message invitant à se connecter (lien vers auth.html)
- Après connexion via le widget de l'en-tête, la page se recharge automatiquement (événement `profile-widget-login`)

`auth.html` redirige automatiquement vers `profile.html` si l'utilisateur est déjà authentifié, ainsi qu'après un login ou une inscription réussie.

## Modèles de données

Les modèles Pydantic définis dans `models.py` :

- **`UserProfile`** : Informations de base de l'utilisateur (langues, objectif de visite, niveau de détail, etc.)
- **`ProfileStats`** : Statistiques globales (nombre d'observations, ressources, thèmes, connaissances par statut)
- **`VisitedResource`** : Une ressource consultée (titre, URI, type, auteur, dates, nombre de consultations)
- **`ThemeStats`** : Statistiques pour un thème (poids d'intérêt, confiance, comptes par type d'observation, comptes par statut de connaissance)
- **`KnowledgeItem`** : Un élément de connaissance avec métadonnées (proposition, résumé, statut, score, confiance, entités, sources)
- **`EntityInfo`** : Information sur une entité liée à une connaissance
- **`SourceInfo`** : Information sur une source d'une connaissance
- **`ObservationRecord`** : Une observation horodatée (famille, type spécifique, contexte, confiance, cibles)
- **`ObservationTargetInfo`** : Une cible d'observation (connaissance, thème ou entité) avec libellé et poids
- **`ObservationTypeStats`** : Nombre d'observations et dernière date par famille (déclarative, comportementale, évaluative)
- **`ThemeKnowledgeGroup`** : Groupe de connaissances pour un thème
- **`UserProfileResponse`** : Réponse complète avec toutes les données du profil

## Base de données

Le fichier `user_profile_views.sql` contient des vues SQL pour faciliter la récupération des données :

1. **`user_profile_stats`** : Statistiques globales par utilisateur
2. **`user_visited_resources`** : Liste des ressources consultées par utilisateur
3. **`user_theme_stats_v2`** : Statistiques par thème pour un utilisateur
4. **`user_knowledge_by_theme`** : Éléments de connaissance groupés par thème
5. **`user_knowledge_with_themes`** : Connaissances de l'utilisateur avec leurs thèmes

*Note* : Ces vues sont optionnelles. Les services peuvent fonctionner sans elles en utilisant des requêtes directes.

## Intégration

### Dans `api_server.py`
```python
# Import du router
from profile.router import router as profile_router

# Inclusion du router
app.include_router(profile_router)
```

### Authentification
La page `/profile` récupère le `user_id` depuis :
1. `request.state.user_id` (si le middleware d'auth place le user_id là)
2. `request.session['user_id']` (si utilisation de sessions)
3. Header `X-User-ID` (pour les requêtes API)

Si aucun `user_id` n'est trouvé, une erreur 401 est retournée.

## Utilisation

### Accès à la page
1. L'utilisateur se connecte via le système d'authentification
2. Il accède à `/profile` dans son navigateur
3. La page affiche toutes ses statistiques et connaissances

### Exemple de requête API
```bash
# Récupérer les données du profil
curl http://localhost:8000/profile/api/user123

# Exporter en CSV
curl http://localhost:8000/profile/api/user123/export/csv -o profile.csv
```

## Dépendances

- FastAPI
- aiomysql
- Jinja2
- Pydantic

Toutes ces dépendances sont déjà présentes dans le projet.

## Personnalisation

### Styles CSS
Les styles sont définis directement dans les templates :
- `profile.j2` : Styles principaux de la page
- `knowledge_item_card.html` : Styles pour les cartes de connaissance
- `resource_card.html` : Styles pour les cartes de ressource
- `theme_stats.html` : Styles pour les cartes de thème

### Couleurs
Les couleurs principales utilisées :
- Rouge bordaux (#b74420) : Couleur principale, en-tête
- Vert (#28a745) : Connaissances maîtrisées
- Jaune (#ffc107) : Connaissances en développement
- Bleu (#17a2b8) : Connaissances rencontrées
- Gris (#6c757d) : Connaissances inconnues

## Tests

Pour tester le module :

1. **Vérifier que les tables de base de données existent** :
   - Exécuter le schéma `user_knowledge_model.sql`
   - Optionnel : Exécuter `user_profile_views.sql` pour les vues

2. **Ajouter des données de test** :
   - Créer un utilisateur dans `user_profiles`
   - Ajouter des observations dans `observations`
   - Ajouter des éléments de connaissance dans `knowledge_items`
   - Relier les observations aux connaissances via `observation_targets`
   - Mettre à jour les états des connaissances via `user_knowledge_states`

3. **Accéder à la page** :
   - Se connecter avec l'utilisateur de test
   - Naviguer vers `/profile`

## Problèmes connus et limitations

1. **Authentification** : Le module dépend du système d'authentification existant pour fournir le `user_id`. Assurez-vous que votre middleware d'auth place correctement le `user_id` dans `request.state` ou `request.session`.

2. **Performances** : Pour les utilisateurs avec beaucoup de données, les requêtes peuvent être lentes. Considérez :
   - Ajouter des indexes supplémentaires
   - Utiliser les vues SQL proposées
   - Implémenter la pagination pour les listes (ressources, thèmes, connaissances)

3. **Export CSV** : Le fichier CSV généré utilise le délimiteur `;` (point-virgule) qui est standard pour les fichiers CSV en français. Pour d'autres locales, vous pouvez modifier le délimiteur dans `page_builder.py`.

4. **Gestion des erreurs** : Les erreurs de base de données sont captées et retournées comme des HTTPException. Vous pouvez personnaliser la gestion des erreurs dans `services.py`.

## Futures améliorations

- [ ] Ajouter des graphiques (Chart.js ou Plotly) pour visualiser les statistiques
- [ ] Implémenter la pagination pour les listes longues
- [ ] Ajouter des filtres (par date, type d'observation, statut de connaissance)
- [ ] Ajouter un système de recherche dans les éléments de connaissance
- [ ] Permettre à l'utilisateur de modifier son profil (objectif, langues, etc.)
- [ ] Ajouter un historique détaillé des interactions
- [ ] Implémenter un système de recommandations basé sur le profil

## Auteurs

Ce module a été créé par Mistral Vibe pour le projet LLMAgents (M3C).
