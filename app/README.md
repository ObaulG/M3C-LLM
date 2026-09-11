*Projet en chantier*

# Explication rapide - Les documents dans la nouvelle BDD

La M3C est composée de 5 `sites`, chacun représentant la traduction dans une langue : 1 : fr; 12 : co; 13: it; 14: en; 15: es.

Au sein de la M3C, on peut accéder à des `item`. Exemple : https://m3c.universita.corsica/s/fr/item/116738 (sur le site en production) ouvre une page offrant l'accès aux métadonnées et au PDF de l' `item_id` 116738.
Ils sont contenus dans la table `item`.

La liste des métadonnées est contenue dans la table `property`. Elle liste les noms `local_name` et leur `id` correspondant :

| local_name      | id  | comment                                                                                                                                     |
|-----------------|-----|---------------------------------------------------------------------------------------------------------------------------------------------|
| title           | 1   | /                                                                                                                                           |
| subject         | 3   | /                                                                                                                                           |
| education_level | 46  | A class of entity, defined in terms of progression through an educational or training contex, for which the described resource is intended. |
| extracted_text  | 214 | Text extracted from a resource.                                                                                                             |
`extracted_text` contient la couche de texte encodée dans un PDF. Elle a été créée pour être manipulée par les différents outils de TAL, et les LLM.

La table `media` répertorie les identifiants des différents médias liés à des `items`. Un item peut avoir plusieurs médias. Un média référence un `item_id`, avec un `media_type` au format MIME, et un `storage_id` qui permet de faire une requête HTTP, en y ajoutant l' `extension` pour récupérer directement le média.

L'item 116738 correspond à un livre qui a été numérisé, et dont le PDF est accessible avec le lien suivant : 
https://m3c.universita.corsica/files/original/dbd5f14a9e6545880b0cd505583ea7d1fe1e8b3d.pdf

On a donc directement concaténé `storage_id` et `extension` pour créer l'argument qui est envoyé.

Attention : les documents ayant un `extracted_text` ne sont pas tous vérifiés. Les documents dont le contenu peut être traité sans problème par les LLM sont stockés dans une constante dans le fichier `database.py`.

La M3C contient également des parcours thématiques. Exemple : https://m3c.universita.corsica/s/fr/page/liberte_corse. 

Ils sont identifiés dans la table `site_page` qui contient un `id`, un champ `title`, un champ `slug` qui représente l'argument à envoyer pour récupérer cette page (ici `liberte_corse`), et l'id est une clef étrangère de `site_page_block`. 

`site_page_block` recense les différents blocs qui composent chaque page. Un bloc a un `layout` et des `data` au format `DC2type:json_array`.

Ce parcours thématique (`page_id` 1625) contient 4 blocs, dont un `html` qui contient ({"html": ...}) le code HTML brut qui est affiché. Il faut donc faire un prétraitement du contenu de ces pages avant de les découper en chunks.

# Pipeline d'indexation

On dispose de documents de tous types, mais tous les documents ont un point commun : les métadonnées. On se propose donc de construire une chaîne de caractères en concaténant toutes les métadonnées et on récupère des embeddings.

Pour tous les documents textuels et vérifiés, on se propose de les découper en *chunks* en suivant une **stratégie**. On rajoutera donc une table `chunking_strategies` qui détaille la méthode employée. Principalement, on découpera par *nombre de caractères* en ajoutant un *overlap*. 

Comme il existe plusieurs sources de texte, on va créer une table `text_documents` qui permet d'identifier tous les documents textuels qui seront utilisés avec les LLM. `source_type` indiquera leur type de provenance (`pdf`, `page`, et peut-être d'autres), et le `source_id` permettra de faire le lien avec la table contenant initialement la ressource. Le texte qui aura été prétraité sera inséré dans la colonne `content`.

Enfin, la table `chunks` contiendra les chunks obtenus lors d'un découpage dans le champ `content`. Il contient la clef étrangère `document_id` qui fait référence au champ `id` de `text_documents`. Pour les documents disposant de pages, le numéro de page du premier caractère/token sera indiqué dans `num_page`. Cela permettra d'indiquer facilement au visiteur la page de la ressource qui a été utilisée pour répondre à sa question.

On utilisera Qdrant pour stocker les embeddings des chunks. Un `chunk` peut disposer de plusieurs embeddings réalisés avec des modèles et/ou dimensions différentes. Avec Qdrant, on peut associer à un point (des embeddings) des métadonnées. On gardera ici l'id du `chunk` ce qui permettra de récupérer les autres informations.

On suivra les étapes suivantes : 

0. Pour l'instant, on récupère seulement les documents identifiés comme vérifiés : dans database/database.py, la constante VALID_TEXT_RESSOURCE_ID indique tous les `resource_id` de la table `value` qui pointe vers des PDF valides ;
1. On récupère les `storage_id` correspondants dans la table `media`.
2. Pour chaque `storage_id` récupéré :
 * On récupère le PDF avec la route https://m3c.universita.corsica/files/original/<storage_id> avec un PyPDFLoader;
 * On découpe le document en chunks avec un `RecursiveCharacterTextSplitter`;
 * Pour chaque chunk numéro `i` :
   * Créer son id `{document_id}-{strategy_id}-{i}`;
   * Tokeniser le chunk;
   * Appeler un embedder;
   * Stocker les métadonnées dans la BDD SQL, et les embeddings avec l'id dans la base de données Qdrant.

# La gestion des documents et des questions 


