# Sauvegarde des pages HTML/CSS statiques

Copie de référence des fichiers servis par `StaticFiles` dans `app/api_server.py`,
prise avant généralisation des templates Jinja2 (`app/templates/`).

- `pages/` : pages du portail (racine de `app/static/`)
- `admin/` : pages admin (`app/static/admin/`)
- `css/` : feuilles de style (`app/static/*.css` et `app/static/admin/admin.css`)

Ces copies ne sont ni compilées ni servies. `app/build_templates.py` écrase
les `.html` de `app/static/`, mais jamais ce dossier.
