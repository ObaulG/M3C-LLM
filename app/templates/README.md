# Templates Jinja2 du portail M3C-LLM

Les pages du portail sont des **templates Jinja2 rendus par des routes FastAPI**
(`app/routers/pages.py`). Ce ne sont plus des fichiers HTML statiques compilés :
chaque page est servie par une route du type `/m3c-chatbot`, `/admin/indexation`, etc.
Les assets (CSS, JS, images) restent servis par `StaticFiles` sous `/static/`.

## Organisation

```
app/
├── routers/
│   └── pages.py              Routes HTML du portail + environnement Jinja2 partagé
├── static/
│   ├── css/                  Un fichier CSS par page (+ theme_cards.css partagé)
│   ├── js/                   Un fichier JS par page (bootstrap + logique inline extraits)
│   └── *.css, *.js           Styles/scripts communs (style.css, models.js, …)
└── templates/
    ├── base.html             Squelette HTML (DOCTYPE, head, body, scripts)
    ├── macros/
    │   ├── ui.html           Macros UI atomiques (btn, badge, spinner, message…)
    │   ├── header_nav.html   En-tête + barre de navigation unifiée
    │   ├── profile.html      Zone profil (mini-form / utilisateur connecté)
    │   ├── question_card.html, knowledge_item_card.html, …
    │   └── theme_stats.html, resource_card.html
    └── pages/                Pages du portail (une par route)
        ├── index.j2
        ├── m3c-chatbot.j2
        ├── profile.j2        (rendue par app/profile/, contexte utilisateur)
        └── admin/indexation.j2, admin/questions_generation.j2, …

```

Les macros sont importées automatiquement comme variables globales par
`app/routers/pages.py` (environnement Jinja2 partagé) : inutile d'écrire
`{% import %}` dans les pages. Toutes les macros sont accessibles directement
(ex. `{{ header(...) }}`, `{{ chat_zone(...) }}`, `{{ question_card(q) }}`).

## Routes

| Route | Template |
|-------|----------|
| `/` | `pages/index.j2` |
| `/tutorials` | `pages/tutorials.j2` |
| `/m3c-chatbot` | `pages/m3c-chatbot.j2` |
| `/m3c-chatbot-history` | `pages/m3c-chatbot-history.j2` |
| `/question-session` | `pages/question_session.j2` |
| `/questions-management` | `pages/questions_management.j2` |
| `/rag-visualization` | `pages/rag_visualization.j2` |
| `/solr-search` | `pages/solr_search.j2` |
| `/auth` | `pages/auth.j2` |
| `/profile` | `pages/profile.j2` (via `app/profile/page_builder.py`) |
| `/admin` | redirection vers `/admin/indexation` |
| `/admin/indexation` | `pages/admin/indexation.j2` |
| `/admin/questions-generation` | `pages/admin/questions_generation.j2` |
| `/admin/knowledge-items-generation` | `pages/admin/knowledge_items_generation.j2` |
| `/admin/message-evaluator` | `pages/admin/message_evaluator_admin.j2` |
| `/admin/observations` | `pages/admin/observations_admin.j2` |
| `/admin/chatbot` | alias de `/admin/indexation` |

## En-tête et barre de navigation unifiés

Toutes les pages du portail sont listées **une seule fois** dans
`macros/header_nav.html` (constante `ALL_PAGES`, href = route absolue).
La macro `header()` génère un en-tête complet : titre + sous-titre + barre de
navigation (avec la page courante marquée `active`) + zone profil.

```jinja
{{ header(
    title='Chatbot RAG M3C',
    subtitle='Système de Questions/Réponses sur documents',
    title_icon='🤖',
    page='/m3c-chatbot',     # route courante (pour le lien actif)
    show_admin=false          # masquer les liens admin sur les pages user
) }}
```

Pour les pages au layout centré (admin, questions_management) :
`{{ header_centered(...) }}` (variante sans `.header-main`).

## Zone profil utilisateur

`macros/profile.html` → `profile_widget()` insérée automatiquement par
`header()`. Affiche :

- **non connecté** : un mini-formulaire de connexion (utilisateur + mot de
  passe) + lien « S'inscrire » (route `/auth`) ;
- **connecté** : le nom de l'utilisateur + lien vers la page de profil
  (`/profile`) + bouton Déconnexion.

La bascule est gérée côté client par `app/static/auth_widget.js`, qui s'appuie
sur le cookie de session `m3c_api_key` (httpOnly, posé par `/api/auth/login`
et `/api/auth/register`, lu par `/api/auth/me` à chaque chargement de page).

Pour inclure le widget sur une page, rien à faire : `header()` l'ajoute.
Pour l'exclure : `include_profile=false`.

## Éléments réutilisables (macros principales)

| Macro | Usage |
|-------|-------|
| `header(...)` / `header_centered(...)` | En-tête + nav unifiée + profil |
| `nav_bar(...)` | Barre de navigation seule |
| `nav_link(href, label, active)` | Lien de navigation |
| `profile_widget()` | Zone profil |
| `message(type, content)` | Bulle de message (`user`/`bot`/`info`/`error`) |
| `chat_zone(container_id, welcome_type, welcome)` | Zone de chat + accueil |
| `message_input(input_id, send_id, send_fn, placeholder)` | Saisie + bouton |
| `bot_response(content, model, total_time, ...)` | Réponse LLM + en-tête |
| `sources_section(sources)` | Bloc des sources citées |
| `loading(id, label)` / `spinner()` | Indicateur de chargement |
| `btn(label, type, ...)` | Bouton (primary/secondary/tertiary/evaluate/save) |
| `feature_card(title, description, href, icon, ...)` | Carte d'accueil |
| `section(id, title, title_icon, extra)` | Section blanche conteneur |
| `status_badge(status)` / `category_badge(category)` | Badges |
| `question_card(question)` | Carte de question + réponses |
| `difficulty_stars(level)` | Étoiles de difficulté |
| `evaluation_section(question_id, has_reference, reference_text)` | Évaluation |
| `empty_state(title, hint)` | État vide |
| `back_button(label, id)` | Bouton de retour |

## Ajouter une page

1. Créer `app/templates/pages/<nom>.j2` (ou `admin/<nom>.j2`).
2. `extends "base.html"` puis remplir les blocks `title`, `styles`,
   `head_scripts`, `body`, `scripts`.
3. Utiliser `{{ header(...) }}` (ou `header_centered`) pour l'en-tête, avec
   `page='<route>'` pour marquer le lien actif.
4. Ajouter la route dans `app/routers/pages.py` et l'entrée correspondante
   dans `ALL_PAGES` (`macros/header_nav.html`) si elle doit apparaître dans la
   navigation.
5. Les assets statiques sont référencés via `{{ static_prefix }}<fichier>`
   (préfixe `/static/`).

La page de profil (`/profile`) est rendue par `app/profile/page_builder.py`,
qui réutilise l'environnement Jinja2 partagé (`routers.pages.get_templates`)
et fournit le contexte utilisateur (statistiques, observations, connaissances).
