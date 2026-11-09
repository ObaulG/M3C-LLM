*Projet en chantier*

# Explication rapide - Les documents dans la nouvelle BDD

La M3C est composée de 5 `sites`, chacun représentant la traduction dans une langue : 1 : fr; 12 : co; 13: it; 14: en; 15: es.

Au sein de la M3C, on peut accéder à des `item`. Exemple : https://m3c.universita.corsica/s/fr/item/116738 (sur le site en production) ouvre une page offrant l'accès aux métadonnées et au PDF de l' `item_id` 116738.
Ils sont contenus dans la table `item` :

+-------+------+------+-----+---------+-------+
| Field | Type | Null | Key | Default | Extra |
+-------+------+------+-----+---------+-------+
| id    | int  | NO   | PRI | NULL    |       |
+-------+------+------+-----+---------+-------+

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

# Indexation RAG des métadonnées

## Principe

Le job d'indexation des métadonnées crée, pour chaque document de la BDD, un embedding à partir de ses métadonnées. Contrairement à l'indexation PDF, ce job ne nécessite pas le fichier : il s'applique à **tous les items présents en base**, qu'ils aient un PDF ou non.

## Schéma des données (M3C / Omeka S)

- `item` : un document. Ne contient qu'un `id`.
- `property` : la liste des métadonnées disponibles (`id`, `local_name`, `label`, `comment`).
- `value` : **toutes les données**. Une ligne = une valeur d'une métadonnée pour un document :
  - `resource_id` : l'id de l'`item` décrit ;
  - `property_id` : la métadonnée (FK vers `property.id`) ;
  - `type` : `literal` (texte dans `value`), `resource` (référence vers un autre item via `value_resource_id`) ou `uri` ;
  - `value` : le texte de la valeur (pour les types `literal`) ;
  - `lang` : langue de la valeur (une même propriété peut exister en plusieurs langues) ;
  - `is_public` : 1 si la valeur est publique.

Les métadonnées d'un document s'obtiennent donc par : `SELECT property_id, value FROM value WHERE resource_id = <id>`.

## Propriétés retenues

La sélection est définie dans la constante `METADATA_PROPERTIES` de `database/database.py` (clé : `property_id`, valeur : `(local_name, label français)`). Les valeurs de type `literal` sont prises en compte ; les types `resource` et `uri` sont ignorés pour l'instant. Seules les valeurs `is_public = 1` sont indexées.

| property_id | local_name | Label dans la chaîne | Remarque |
|---|---|---|---|
| 1 | title | Titre | |
| 117 | shortTitle | Titre court | |
| 17 | alternative | Titre alternatif | |
| 2 | creator | Auteur | fusionné dans la ligne `Auteurs` |
| 6 | contributor | Contributeur | fusionné dans la ligne `Auteurs` |
| 66 | editor | Éditeur scientifique | fusionné dans la ligne `Auteurs` |
| 85 | translator | Traducteur | |
| 94 | edition | Édition | |
| 7 | date | Date | |
| 8 | type | Type | |
| 12 | language | Langue | |
| 5 | publisher | Éditeur | |
| 16 | audience | Audience | |
| 46 | educationLevel | Niveau éducatif | |
| 40 | spatial | Couverture spatiale | |
| 41 | temporal | Couverture temporelle | |
| 260 | location | Lieu | |
| 3 | subject | Mots-clés | multi-valué, séparateur `, ` |
| 19 | abstract | Résumé | prioritaire sur `description` |
| 4 | description | Résumé | utilisé seulement si `abstract` absent |

Sont volontairement exclues : `extracted_text` (214) et `text` (185) (contenu, pas métadonnées), `format`/`extent`/`numPages`/`identifier`/`isbn`/`doi`/`uri` (techniques), `rights`/`license`/`accessRights` (juridiques), `relation` et dérivées (références vers d'autres resources), `tag`/`theme`/`category` (219-221, redondantes avec `subject`).

## Format de la chaîne de métadonnées

Pour chaque document, `build_metadata_string` (dans `indexing/services.py`) construit une chaîne, **une métadonnée par ligne** au format `Label: valeur` :

- les lignes dont la valeur est absente ou vide sont omises ;
- `creator`, `contributor` et `editor` sont fusionnés sur une seule ligne `Auteurs` (séparateur `; `) ;
- les propriétés multi-valuées sont séparées par `, ` ;
- la ligne `Résumé` utilise `abstract` si présent, sinon `description` ;
- chaque valeur est nettoyée : trim + espaces/retours à la ligne multiples réduits à un seul espace.

Exemple :

```
Titre: Le Corse dans tous ses états
Auteurs: Marie-Ange Geronimi; Jean-Marc Comiti
Date: 2019
Type: Text
Langue: corse
Éditeur: Università di Corsica
Niveau éducatif: Licence
Mots-clés: langue corse, sociolinguistique, enseignement
Résumé: Étude sociolinguistique de la place de la langue corse dans l'enseignement supérieur.
```

Un document dont la chaîne finale est vide (aucune métadonnée publique) est marqué `failed` avec l'erreur « La chaîne de métadonnées est vide ».

## Stockage Qdrant

- Collection : `MD-<embedder>-<dimension>` (une collection par modèle d'embedding).
- Un document = exactement un point par collection. L'ID du point est déterministe : `uuid5(NAMESPACE_URL, "metadata-<resource_id>")`, donc **ré-indexer un document écrase son embedding précédent** (upsert idempotent, jamais de doublon).
- Payload du point : `document_id` (`metadata-<resource_id>`), `model_name`, `source` (`metadata`), `resource_id`, `content` (la chaîne de métadonnées complète).

## Lancer le job

Depuis la page d'admin « Indexation des Documents », option « Tous les items de la BDD - Métadonnées », ou via l'API :

```bash
curl -X POST "http://localhost:8000/api/admin/documents/index" \
  -H "Content-Type: application/json" \
  -d '{"indexation_type": "all-items-metadata", "embedder_name": "mistral-embed"}'
```

Types d'indexation disponibles pour les métadonnées :

- `all-items-metadata` : **tous les items de la BDD** (tout `resource_id` ayant au moins une valeur publique dans `value`) ;
- `metadata-only` / `all-metadata` : les `VALID_TEXT_RESOURCE_ID` (PDFs vérifiés) ;
- `selected-metadata` : une liste explicite de `resource_ids`.

Le job est asynchrone, résumable (progression par `resource_id` ; les documents déjà `completed` sont sautés à la reprise) et traite les documents par lots de 32 (un appel `embed_batch` et un upsert Qdrant par lot). Suivi : `GET /api/admin/documents/index/job/{job_id}/status`.

## Note pour les développeurs et les agents IA

- La liste des documents à indexer en mode « tous les items » vient de `get_all_document_ids` (`SELECT DISTINCT resource_id FROM value WHERE is_public = 1`) : un item sans aucune valeur publique n'est pas indexé et ne peut pas l'être (chaîne vide).
- Invariant : un document a au plus un embedding de métadonnées par collection `MD-*` ; ré-exécuter le job est toujours sûr (upsert déterministe).
- Pour ajouter une métadonnée à la chaîne : ajouter l'entrée dans `METADATA_PROPERTIES` (`database/database.py`) puis la ligne correspondante dans `build_metadata_string` (`indexing/services.py`) ; les deux doivent rester synchrones, et ce README doit être mis à jour.

# La gestion des documents et des questions 


