# Introduction

M3C-LLM est un prototype personnel de développement d'outils liés à la M3C (Médiathèque culturelle de la Corse et des Corses) (https://m3c.universita.corsica/s/fr/page/home). 

Deux prototypes sont disponibles :
- M3C-chatbot, une implémentation classique de chatbot basé sur les LLM, implémentant le RAG à partir d'une BDD PostGreSQL.
- Question-session, une expérimentation où un utilisateur choisit un document, et l'application pose une série de questions (définie manuellement pour l'instant) à l'utilisateur. Les questions et les réponses de références sont au départ toutes générées par LLM, mistral-medium ici, et la réponse rédigée de l'utilisateur est évaluée à partir d'un ou plusieurs LLM.

# Mise en place

## Variables d'environnement

La configuration se fait via des variables d'environnement (voir `.env.example`
pour le développement local et `.env.docker` pour le déploiement en conteneur).
Les principales sont :

| Variable | Défaut | Description |
|----------|--------|-------------|
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | — | Connexion à la base de données MySQL |
| `QDRANT_HOST` / `QDRANT_PORT` | — | Connexion à la base vectorielle Qdrant |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | Hôte et port du serveur API FastAPI |
| `MISTRAL_API_KEY` | — | Clé API Mistral du serveur |
| `GROQ_API_KEY` / `GEMINI_API_KEY` | — | Clés API optionnelles (Groq, Google) |
| `REQUIRE_USER_MISTRAL_API_KEY` | `true` | Oblige les utilisateurs normaux à fournir leur propre clé Mistral |
| `SOLR_ENABLED` | `0` | Active Solr (`1`) ou non (`0`) |
| `WITH_LOCAL_LLM` | `true` | Active les modèles locaux (Ollama) et les mesures GPU (`torch`, `pynvml`). Quand elle vaut `false`, les modèles locaux ne sont pas proposés sur les pages du site (route `/api/models`) et les librairies GPU ne sont pas importées — utile pour un déploiement sans carte graphique |
| `LOG_LEVEL` | `INFO` | Niveau de log du serveur |

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





