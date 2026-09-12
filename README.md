# Introduction

M3C-LLM est un prototype personnel de développement d'outils liés à la M3C (Médiathèque culturelle de la Corse et des Corses) (https://m3c.universita.corsica/s/fr/page/home). 

Deux prototypes sont disponibles :
- M3C-chatbot, une implémentation classique de chatbot basé sur les LLM, implémentant le RAG à partir d'une BDD PostGreSQL.
- Question-session, une expérimentation où un utilisateur choisit un document, et l'application pose une série de questions (définie manuellement pour l'instant) à l'utilisateur. Les questions et les réponses de références sont au départ toutes générées par LLM, mistral-medium ici, et la réponse rédigée de l'utilisateur est évaluée à partir d'un ou plusieurs LLM.

# Comptes utilisateurs

Une table `users` (voir `app/database/create_user_question_tables.sql`) permet de gérer les comptes :

| Colonne         | Type            | Description                                             |
|-----------------|-----------------|---------------------------------------------------------|
| user_id         | SERIAL (PK)     | Identifiant de l'utilisateur                            |
| username        | VARCHAR(255)    | Nom d'utilisateur, unique                               |
| email           | VARCHAR(255)    | Email, unique                                           |
| password_hash   | VARCHAR(255)    | Hash du mot de passe (PBKDF2-SHA256 + sel)               |
| role            | VARCHAR(50)     | `admin`, `validator` ou `user`                          |
| is_active       | BOOLEAN         | Compte actif (par défaut `TRUE`)                        |
| created_at      | TIMESTAMP       | Date de création                                        |

La page `app/static/auth.html` (accessible à `/static/auth.html`) permet de :
- créer un compte (`/api/auth/register`) ;
- se connecter (`/api/auth/login`), ce qui délivre une clé API conservée côté client ;
- récupérer l'utilisateur courant (`/api/auth/me`) ;
- se déconnecter (`/api/auth/logout`).

Les sessions sont volontairement gardées en mémoire côté serveur (prototype) : redémarrer l'API invalide les clés émises. La table `users` doit être créée au préalable via `app/database/create_question_db.py`.

# Références expérimentation

L'expérimentation s'est basée sur le prototype Question-session, où 8 personnes se sont prêtées au jeu. Deux ressources de références, accessible selon nous à tous les publics ont été choisies :
- *Lochi mondu*, Alain di Meglio (https://m3c.universita.corsica/s/fr/item/116738);
- *Atlas de la Corse contemporaine*, Didier Rey (https://m3c.universita.corsica/s/fr/item/116782)

Les questions et réponses référence de l'expérimentation sont disponibles dans le fichier question-answer-reference.csv, dans l'ordre donné ci-dessous :
- Lochi mondu :[249, 370, 737, 786, 115];
- Atlas de la Corse contemporaine : [2021, 1224, 1506, 1525, 1757].

