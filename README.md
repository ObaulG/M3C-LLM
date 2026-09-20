# Introduction

M3C-LLM est un prototype personnel de développement d'outils liés à la M3C (Médiathèque culturelle de la Corse et des Corses) (https://m3c.universita.corsica/s/fr/page/home). 

Deux prototypes sont disponibles :
- M3C-chatbot, une implémentation classique de chatbot basé sur les LLM, implémentant le RAG à partir d'une BDD PostGreSQL.
- Question-session, une expérimentation où un utilisateur choisit un document, et l'application pose une série de questions (définie manuellement pour l'instant) à l'utilisateur. Les questions et les réponses de références sont au départ toutes générées par LLM, mistral-medium ici, et la réponse rédigée de l'utilisateur est évaluée à partir d'un ou plusieurs LLM.

# Mise en place


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





