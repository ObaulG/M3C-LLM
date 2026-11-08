# Introduction

M3C-LLM est un prototype de développement d'outils basés sur les IA génératives pour la M3C (Médiathèque culturelle de la Corse et des Corses) (https://m3c.universita.corsica/s/fr/page/home). 

Parmi les fonctionnalités disponibles :
- M3C-chatbot, une implémentation classique de chatbot basé sur les LLM, implémentant le RAG à partir d'une BDD MySQL et Qdrant.
- Question-session, une expérimentation où un utilisateur choisit un document, et l'application pose une série de questions (définie manuellement pour l'instant) à l'utilisateur. Les questions et les réponses de références sont au départ toutes générées par LLM, et la réponse rédigée de l'utilisateur est évaluée à partir d'un ou plusieurs LLM.
- Une page de gestion des questions, permettant d'éditer, de créer des questions sur des morceaux de documents existants.

Pour les détails techniques de l'application, consulter les différents fichiers README à l'intérieur de ``app``.




