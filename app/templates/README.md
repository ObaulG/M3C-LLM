# Templates Jinja2 du portail M3C-LLM

Cette bibliothèque de templates Jinja2 permet de **réutiliser les éléments
d'affichage** communs à toutes les pages du portail (en-tête, barre de
navigation, zone de message, cartes de question, boutons, badges, etc.).

## Organisation

```
app/templates/
├── base.html                    Squelette HTML (DOCTYPE, head, body, scripts)
├── macros/
│   ├── ui.html                  Macros UI atomiques (btn, badge, spinner,
│   │                            message, message_input, chat_zone, sources…)
│   ├── header_nav.html          En-tête + barre de navigation unifiée
│   ├── profile.html             Zone profil (mini-form / utilisateur connecté)
│   └── question_card.html       Carte de question + section d'évaluation
└── pages/                       Pages du portail (une par route)
    ├── index.j2
    ├── m3c-chatbot.j2
    └── admin/indexation.j2 …
```

Les macros sont importées automatiquement comme variables globales par
`app/build_templates.py` : inutile d'écrire `{% import %}` dans les pages.
Toutes les macros sont accessibles directement (ex. `{{ header(...) }}`,
`{{ chat_zone(...) }}`, `{{ question_card(q) }}`).

## En-tête et barre de navigation unifiés

Toutes les pages du portail sont listées **une seule fois** dans
`macros/header_nav.html` (constante `ALL_PAGES`). La macro `header()` génère
un en-tête complet : titre + sous-titre + barre de navigation (toutes les
pages, avec la page courante marquée `active`) + zone profil.

```jinja
{{ header(
    title='Chatbot RAG M3C',
    subtitle='Système de Questions/Réponses sur documents',
    title_icon='🤖',
    page='m3c-chatbot.html',      # nom du fichier courant (pour le lien actif)
    page_dir='root',              # 'root' ou 'admin' (ajuste les liens relatifs)
    show_admin=false              # masquer les liens admin sur les pages user
) }}
```

Pour les pages au layout centré (admin, question_session) :
`{{ header_centered(...) }}` (variante sans `.header-main`).

## Zone profil utilisateur

`macros/profile.html` → `profile_widget()` insérée automatiquement par
`header()`. Affiche :

- **non connecté** : un mini-formulaire de connexion (utilisateur + mot de
  passe) + lien « S'inscrire » ;
- **connecté** : le nom de l'utilisateur + lien vers la page de profil
  (`auth.html`) + bouton Déconnexion.

La bascule est gérée côté client par `app/static/auth_widget.js`, qui réutilise
le token stocké dans `localStorage('m3c_api_key')` et les endpoints existants
(`/api/auth/login`, `/api/auth/me`, `/api/auth/logout`). La session reste ainsi
cohérente avec `auth.html`.

Pour inclure le widget sur une page, rien à faire : `header()` l'ajoute.
Pour l'exclure : `include_profile=false`.

## Éléments réutilisables (macros principales)

| Macro | Usage |
|-------|-------|
| `header(...)` / `header_centered(...)` | En-tête + nav unifiée + profil |
| `nav_bar(...)` | Barre de navigation seule |
| `nav_link(href, label, active)` | Lien de navigation |
| `profile_widget(page_dir)` | Zone profil |
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

## Build : compilation en HTML statique

Le portail est servi par `StaticFiles` (FastAPI) ; les pages sont donc des
fichiers HTML statiques. Le script `app/build_templates.py` compile les
templates `.j2` en `.html` dans `app/static/` (et `app/static/admin/`), en
conservant les URLs existantes.

```bash
# Toutes les pages
python3 app/build_templates.py

# Une page précise
python3 app/build_templates.py index.j2
```

`static_prefix` ('' à la racine, '../' pour les pages admin) est passé
automatiquement au template pour résoudre correctement `style.css`,
`auth_widget.js` et les liens relatifs.

## Convertir une page existante

1. Créer `app/templates/pages/<nom>.j2` (ou `admin/<nom>.j2`).
2. `extends "base.html"` puis remplir les blocks `title`, `styles`,
   `head_scripts`, `body`, `scripts`.
3. Remplacer le bloc en-tête/nav par `{{ header(...) }}` (ou
   `header_centered`).
4. Remplacer les zones répétitives par les macros (`chat_zone`,
   `message_input`, `feature_card`, `question_card`, etc.).
5. Ajouter la page à la liste `PAGES` dans `app/build_templates.py` si
   nécessaire, puis lancer le build.

Les fichiers HTML d'origine peuvent être conservés comme sauvegarde (le build
les écrase).
