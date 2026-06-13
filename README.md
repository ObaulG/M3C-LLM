# Introduction

M3C-LLM est un prototype personnel de développement d'outils liés à la M3C (Médiathèque culturelle de la Corse et des Corses) (https://m3c.universita.corsica/s/fr/page/home). 

Deux prototypes sont disponibles :
- M3C-chatbot, une implémentation classique de chatbot basé sur les LLM, implémentant le RAG à partir d'une BDD PostGreSQL.
- Question-session, une expérimentation où un utilisateur choisit un document, et l'application pose une série de questions (définie manuellement pour l'instant) à l'utilisateur. Les questions et les réponses de références sont au départ toutes générées par LLM, mistral-medium ici, et la réponse rédigée de l'utilisateur est évaluée à partir d'un ou plusieurs LLM.

# Références expérimentation

L'expérimentation s'est basée sur le prototype Question-session, où 8 personnes se sont prêtées au jeu. Deux ressources de références, accessible selon nous à tous les publics ont été choisies :
- *Lochi mondu*, Alain di Meglio (https://m3c.universita.corsica/s/fr/item/116738);
- *Atlas de la Corse contemporaine*, Didier Rey (https://m3c.universita.corsica/s/fr/item/116782)

Les questions et réponses référence de l'expérimentation sont disponibles dans le fichier question-answer-reference.csv, dans l'ordre donné ci-dessous :
- Lochi mondu :[249, 370, 737, 786, 115];
- Atlas de la Corse contemporaine : [2021, 1224, 1506, 1525, 1757].



