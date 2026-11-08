# Introduction

M3C-LLM est un prototype personnel de développement d'outils liés à la M3C (Médiathèque culturelle de la Corse et des Corses) (https://m3c.universita.corsica/s/fr/page/home). 

Deux prototypes sont disponibles :
- M3C-chatbot, une implémentation classique de chatbot basé sur les LLM, implémentant le RAG à partir d'une BDD PostGreSQL.
- Question-session, une expérimentation où un utilisateur choisit un document, et l'application pose une série de questions (définie manuellement pour l'instant) à l'utilisateur. Les questions et les réponses de références sont au départ toutes générées par LLM, mistral-medium ici, et la réponse rédigée de l'utilisateur est évaluée à partir d'un ou plusieurs LLM.

# Mise en place

## Installation

### Option 1 : Avec Docker (recommandé)

1. **Prérequis** : Docker (>= 20.10) et Docker Compose (>= 1.29), 4 Go de RAM et 10 Go d'espace disque recommandés.

2. **Configurer les variables d'environnement** :

   ```bash
   cp .env.docker .env
   # puis modifiez les valeurs si nécessaire (notamment DB_PASSWORD)
   ```

   Les principales variables sont décrites dans `.env.example` : `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `QDRANT_HOST`, `QDRANT_PORT`, `API_HOST`, `API_PORT`, ainsi que les clés API (`MISTRAL_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`).

3. **Démarrer les services** (Qdrant + application FastAPI ; la base MySQL est externe) :

   ```bash
   docker-compose up -d --build
   ```

4. **Créer les tables MySQL manquantes** (si besoin) via `docker/mysql/migrate_missing_tables.sql`.

5. **Vérifier l'installation** :

   ```bash
   docker-compose ps
   curl http://localhost:8000/api/health
   curl http://localhost:6333/readyz
   ```

   L'application est alors disponible sur http://localhost:8000 et sa documentation interactive (Swagger) sur http://localhost:8000/docs.

> Un tutoriel complet (dépannage, commandes quotidiennes, production) est disponible dans [docker/README.md](docker/README.md).

### Option 2 : Installation locale (sans Docker)

1. **Prérequis** : Python 3.12, une base MySQL accessible et un serveur Qdrant (local ou distant).

2. **Installer les dépendances** :

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows : .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configurer l'environnement** : créez un fichier `.env` à partir de `.env.example`, en pointant `DB_HOST` et `QDRANT_HOST` vers vos serveurs locaux.

4. **Initialiser la base de données** : créez la base `m3c_database` et exécutez les scripts SQL de `app/database/sql_tables_scripts/` (voir la section « Structure de la base de données » ci-dessous).

5. **Lancer l'application** :

   ```bash
   cd app
   PYTHONPATH=.. python api_server.py   # Windows (PowerShell) : $env:PYTHONPATH=".."; python api_server.py
   ```

   L'API démarre sur `http://localhost:8000` (documentation sur `/docs`).

## Structure de la base de données

### Table `user`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | int | NO | PRI | NULL | auto_increment |
| email | varchar(190) | NO | UNI | NULL | |
| name | varchar(190) | NO | | NULL | |
| created | datetime | NO | | NULL | |
| modified | datetime | YES | | NULL | |
| password_hash | varchar(60) | YES | | NULL | |
| role | varchar(190) | NO | | NULL | |
| is_active | tinyint(1) | NO | | NULL | |

> **Note**: Le champ `name` correspond au nom d'utilisateur (username).

> **Note**: La clé API Mistral personnelle (rôles user/guest) est stockée dans
> la table dédiée `user_mistral_api_keys` (voir
> `app/database/sql_tables_scripts/create_user_mistral_api_keys.sql`), séparée
> de la table `user`.





