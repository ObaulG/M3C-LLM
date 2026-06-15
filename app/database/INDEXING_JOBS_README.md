# Gestion des Jobs d'Indexation - Documentation

## Introduction

Ce système permet de gérer l'indexation asynchrone des PDFs depuis la base de données M3C, avec possibilité de reprise en cas d'interruption.

## Prérequis

### 1. Créer la table des jobs

Avant d'utiliser les fonctionnalités de job, exécutez le script SQL suivant dans votre base de données MySQL (m3c_database) :

```bash
mysql -u OBL -p m3c_database < app/database/create_indexing_jobs_table.sql
```

Ou exécutez le contenu du fichier `create_indexing_jobs_table.sql` manuellement dans votre client MySQL.

### 2. Dépendances Python

Les dépendances suivantes doivent être installées :
- `aiohttp` - pour le téléchargement asynchrone des PDFs
- `langchain-community` - pour PyPDFLoader
- `langchain-text-splitters` - pour RecursiveCharacterTextSplitter

Elles sont normalement déjà installées dans votre environnement.

## Utilisation

### Démarrer un job d'indexation

Pour démarrer un nouveau job qui va télécharger les PDFs depuis M3C, les découper en chunks et générer les embeddings :

```bash
curl -X POST "http://localhost:8000/api/admin/documents/index/job/start" \
  -H "Content-Type: application/json" \
  -d '{"indexation_type": "pdf-from-m3c", "chunk_size": 2700, "chunk_overlap": 400}'
```

**Paramètres :**
- `indexation_type` (requis): Doit être "pdf-from-m3c"
- `chunk_size` (optionnel): Taille des chunks en caractères (défaut: 2700)
- `chunk_overlap` (optionnel): Recouvrement entre chunks (défaut: 400)
- `force_restart` (optionnel): Si true, annule un job existant et en démarre un nouveau (défaut: false)

**Réponse :**
```json
{
  "success": true,
  "job_id": "uuid-du-job",
  "message": "Job uuid-du-job démarré en arrière-plan",
  "job_status": {
    "job_id": "uuid-du-job",
    "job_type": "pdf-from-m3c",
    "status": "pending",
    "total_items": 19,
    "processed_items": 0,
    "progress": {},
    "parameters": {"chunk_size": 2700, "chunk_overlap": 400},
    "created_at": "2024-01-01T12:00:00",
    "updated_at": "2024-01-01T12:00:00",
    "error_message": null
  }
}
```

### Vérifier le statut d'un job

```bash
curl -X GET "http://localhost:8000/api/admin/documents/index/job/{job_id}/status"
```

**Réponse :**
```json
{
  "job_id": "uuid-du-job",
  "job_type": "pdf-from-m3c",
  "status": "running",
  "total_items": 19,
  "processed_items": 5,
  "progress": {
    "116723": {"status": "completed", "chunks_count": 12, "embeddings_count": 12, "processed_at": "..."},
    "116789": {"status": "completed", "chunks_count": 8, "embeddings_count": 8, "processed_at": "..."},
    "116805": {"status": "processing", "started_at": "..."},
    "116729": {"status": "failed", "error": "Aucun PDF trouvé...", "processed_at": "..."}
  },
  "parameters": {"chunk_size": 2700, "chunk_overlap": 400},
  "created_at": "2024-01-01T12:00:00",
  "updated_at": "2024-01-01T12:05:00",
  "error_message": null
}
```

Le champ `progress` contient le statut détaillé pour chaque resource_id (issu de VALID_TEXT_RESOURCE_ID).

### Lister tous les jobs

```bash
curl -X GET "http://localhost:8000/api/admin/documents/index/jobs"
```

**Paramètres optionnels :**
- `status_filter`: Filtrer par statut (ex: `?status_filter=running`)

**Réponse :**
```json
{
  "jobs": [
    {
      "job_id": "uuid-1",
      "job_type": "pdf-from-m3c",
      "status": "completed",
      ...
    },
    {
      "job_id": "uuid-2",
      "job_type": "pdf-from-m3c",
      "status": "running",
      ...
    }
  ],
  "count": 2
}
```

### Annuler un job

```bash
curl -X POST "http://localhost:8000/api/admin/documents/index/job/{job_id}/cancel"
```

**Réponse :**
```json
{
  "success": true,
  "job_id": "uuid-du-job",
  "message": "Job uuid-du-job annulé avec succès",
  "job_status": {
    "status": "cancelled",
    ...
  }
}
```

### Utilisation via l'endpoint existant

Vous pouvez aussi utiliser l'endpoint existant `/api/admin/documents/index` avec le nouveau type :

```bash
curl -X POST "http://localhost:8000/api/admin/documents/index" \
  -H "Content-Type: application/json" \
  -d '{"indexation_type": "pdf-from-m3c", "chunk_size": 2700, "chunk_overlap": 400}'
```

Cela créera un job et retournera immédiatement avec le job_id.

## Fonctionnement interne

### Étapes du traitement

1. **Création du job** : Un enregistrement est créé dans la table `indexing_jobs` avec statut "pending"
2. **Téléchargement** : Pour chaque resource_id dans VALID_TEXT_RESOURCE_ID, le PDF est téléchargé depuis M3C
3. **Découpage** : Le PDF est chargé avec PyPDFLoader et découpé avec RecursiveCharacterTextSplitter
4. **Sauvegarde** : Les chunks sont sauvegardés dans la table MySQL `chunks`
5. **Embeddings** : Les embeddings sont générés et sauvegardés dans Qdrant
6. **Mise à jour** : La progression est régulièrement sauvegardée dans la base

### Reprise automatique

Le système vérifie automatiquement la progression existante avant de traiter chaque resource_id :
- Si un resource_id a déjà été traité avec succès (`status: "completed"`), il est ignoré
- Si un resource_id a échoué, il est retraité
- La progression est sauvegardée toutes les 3 ressources ou en cas d'erreur

### Gestion des erreurs

- Les erreurs par resource_id sont stockées dans le champ `progress`
- Le job continue même si certains PDFs échouent
- Le statut final du job est "completed" si tous les resource_id ont réussi, sinon "failed"

## Monitoring

Vous pouvez surveiller la progression via :
- Le endpoint `/api/admin/documents/index/job/{job_id}/status`
- La table MySQL `indexing_jobs`
- Les logs du serveur

## Structure des données

### Table indexing_jobs

| Colonne | Type | Description |
|---------|------|-------------|
| job_id | VARCHAR(36) | UUID unique |
| job_type | VARCHAR(50) | Type de job (ex: "pdf-from-m3c") |
| status | ENUM | Statut: pending, running, completed, failed, cancelled |
| created_at | TIMESTAMP | Date de création |
| updated_at | TIMESTAMP | Dernière mise à jour |
| total_items | INT | Nombre total de resource_id à traiter |
| processed_items | INT | Nombre de resource_id traités |
| progress | JSON | Progression détaillée |
| parameters | JSON | Paramètres du job |
| error_message | TEXT | Message d'erreur global |

### Format de progress

```json
{
  "116723": {
    "status": "completed",
    "chunks_count": 12,
    "embeddings_count": 12,
    "processed_at": "2024-01-01T12:00:00"
  },
  "116789": {
    "status": "failed",
    "error": "Erreur de téléchargement",
    "processed_at": "2024-01-01T12:01:00"
  }
}
```

## Dépannage

### Problèmes courants

1. **"Un job est déjà en cours"** : Utilisez `force_restart=true` ou attendez la fin du job actuel
2. **"Aucun PDF trouvé pour resource_id X"** : Vérifiez que le resource_id existe dans la table `media` avec extension 'pdf'
3. **"Erreur téléchargement PDF"** : Vérifiez que le serveur M3C est accessible et que l'URL est valide

### Vérifier les logs

Les logs du serveur FastAPI contiendront des informations détaillées sur les erreurs.

### Tester manuellement

Vous pouvez tester les fonctions individuellement :

```python
# Tester la récupération de l'URL
from database.database import get_pdf_url_for_resource
url = await get_pdf_url_for_resource(116738)
print(url)  # Doit afficher une URL valide

# Tester le téléchargement
import aiohttp
async with aiohttp.ClientSession() as session:
    async with session.get(url) as response:
        print(response.status)  # Doit être 200
```

## Performances

- **Timeout par PDF** : 5 minutes (configurable)
- **Mise à jour de progression** : Toutes les 3 ressources
- **Taille moyenne des chunks** : ~2700 caractères avec overlap de 400
- **Nombre de resource_id** : 19 (issus de VALID_TEXT_RESOURCE_ID)

## Sécurité

- Les jobs sont associés à un UUID unique
- La reprise est automatique et sûre
- Les fichiers temporaires sont nettoyés après traitement
- Les erreurs sont isolées par resource_id
