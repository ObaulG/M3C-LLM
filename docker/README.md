# Configuration Docker pour LLMAgents

Ce dossier contient la configuration Docker pour conteneuriser l'application LLMAgents avec Qdrant et, par défaut, une base MySQL locale (service `mysql`). Une base MySQL **externe** (serveurs M3C) reste possible en pointant `DB_HOST` vers le serveur concerné. Un dump SQL de la base M3C initiale peut être importé via `docker/mysql/import_m3c_dump.sh` (voir [Importer un dump de la base M3C](#-importer-un-dump-de-la-base-m3c)).

## 📖 Sommaire

- [Prérequis](#prérequis)
- [🚀 Tutoriel : Mise en place complète avec Docker](#-tutoriel--mise-en-place-complète-avec-docker)
- [📚 Configuration de référence](#-configuration-de-référence)
- [📥 Importer un dump de la base M3C](#-importer-un-dump-de-la-base-m3c)
- [🎯 Commandes de référence rapide](#-commandes-de-référence-rapide)
- [📊 Services disponibles](#-services-disponibles)
- [👨‍💻 Développement](#-développement)
- [🏭 Production](#-production)
- [🛠️ Dépannage](#-dépannage)
- [🔒 Sécurité](#-sécurité)
- [💾 Structure des données](#-structure-des-données)

---

## Structure

```
docker/
├── mysql/
│   ├── init.sql                  # Script d'initialisation de la base de données MySQL (exécuté au 1er démarrage du conteneur mysql)
│   ├── migrate_missing_tables.sql # Création des tables manquantes (base externe ou dump M3C importé)
│   └── import_m3c_dump.sh        # Import d'un dump SQL de la base M3C initiale dans le MySQL Docker
├── qdrant/
│   └── init.sh           # Création des collections Qdrant au démarrage (service qdrant-init)
├── app/
│   └── entrypoint.sh     # Script d'entrée pour l'application
└── README.md             # Ce fichier
```

## Prérequis

- Docker (version 20.10 ou supérieure)
- Docker Compose (version 1.29 ou supérieure)
- Windows, Linux ou macOS
- Minimum **4 Go de RAM** et **10 Go d'espace disque** recommandés

---

## 🚀 Tutoriel : Mise en place complète avec Docker

Ce tutoriel vous guide pas à pas, de l'installation à la mise en production.

### Étape 0 : Vérification de l'environnement ⏱️ 5-10 minutes

Avant de commencer, assurez-vous que Docker et Docker Compose sont correctement installés :

```bash
# Vérifier Docker
docker --version
# Devrait afficher : Docker version 20.10.x ou supérieur

# Vérifier Docker Compose
docker-compose --version
# Devrait afficher : docker-compose version 1.29.x ou supérieur

# Vérifier l'espace disque et mémoire
docker info | grep -i "memory\|disk"
```

**Si Docker n'est pas installé** :
- [Windows/Mac](https://www.docker.com/products/docker-desktop) : Télécharger Docker Desktop
- [Linux](https://docs.docker.com/engine/install/) : Suivre les instructions officielles

**Positionnez-vous dans le projet** :
```bash
cd /chemin/vers/LLMAgents
```

---

### Étape 1 : Configuration des variables d'environnement ⏱️ 5 minutes

L'application utilise des variables d'environnement pour la configuration.

#### Pour le développement/local :
```bash
# Copier le fichier d'exemple
cp .env.docker .env

# Le fichier .env contient déjà les valeurs par défaut pour Docker
# Vous pouvez les modifier si nécessaire
nano .env  # ou utilisez votre éditeur préféré
```

#### Variables importantes à connaître :

| Variable | Valeur par défaut | Description |
|----------|------------------|-------------|
| `DB_HOST` | mysql | Hôte MySQL : `mysql` pour le service Docker local, sinon l'hôte de la base **externe** (serveurs M3C) |
| `MYSQL_ROOT_PASSWORD` | root | Mot de passe root du conteneur MySQL local (optionnel) |
| `MYSQL_HOST_PORT` | 3306 | Port publié sur la machine hôte pour le MySQL Docker local |
| `SOLR_ENABLED` | 0 | Active Solr (désactivé par défaut, non déployé en conteneur) |
| `REQUIRE_USER_MISTRAL_API_KEY` | true | Oblige les utilisateurs `user`/`guest` à fournir leur propre clé Mistral |
| `DB_PORT` | 3306 | Port MySQL |
| `DB_NAME` | m3c_database | Nom de la base de données |
| `DB_USER` | OBL | Utilisateur MySQL |
| `DB_PASSWORD` | azerty | ⚠️ **Mot de passe MySQL (à changer !)** |
| `QDRANT_HOST` | qdrant | Nom du service Qdrant |
| `QDRANT_PORT` | 6333 | Port Qdrant |
| `API_HOST` | 0.0.0.0 | Hôte de l'API |
| `API_PORT` | 8000 | Port de l'application |

> **⚠️ Pour la production** : Vérifiez que `DB_HOST`, `DB_USER` et `DB_PASSWORD` pointent vers la base MySQL externe et ne sont pas les valeurs d'exemple.

---

### Étape 2 : Démarrage des conteneurs ⏱️ 5-10 minutes

Lancez tous les services avec une seule commande :

```bash
docker-compose up -d --build
```

**Explication de la commande** :
- `up` : Démarre les conteneurs
- `-d` : Mode détaché (en arrière-plan)
- `--build` : Reconstruit les images si nécessaire

**Que se passe-t-il ?**
1. Docker télécharge les images de base (Python, Qdrant)
2. Construit l'image de votre application
3. Crée les volumes pour les données persistantes
4. Démarre les services dans l'ordre : Qdrant → qdrant-init (création des collections) → Application
5. L'application attend que la base MySQL (`DB_HOST`) et Qdrant soient joignables avant de démarrer

> **💾 Base MySQL locale (défaut)** : avec `DB_HOST=mysql` (`.env.docker`), le service `mysql` du `docker-compose.yml` héberge la base en conteneur. Au **premier démarrage** (volume `mysql_data` vide), `docker/mysql/init.sql` crée la base, l'utilisateur et les tables du projet.
>
> **⚠️ Base MySQL externe** : pour pointer vers la base des serveurs M3C, changez `DB_HOST` dans `.env`. La base n'est ni créée ni initialisée par Docker ; si des tables manquent, exécutez `docker/mysql/migrate_missing_tables.sql` manuellement sur le serveur MySQL.
>
> **📥 Données M3C initiales** : pour importer un dump SQL de la base M3C initiale dans le MySQL Docker, voir [Importer un dump de la base M3C](#-importer-un-dump-de-la-base-m3c).

**Premier démarrage** : Peut prendre 2-5 minutes selon votre connexion Internet et les performances de votre machine.

**Pour suivre la progression** :
```bash
# Voir les logs en temps réel
docker-compose logs -f

# Arrêter l'affichage des logs : Ctrl+C
```

---

### Étape 3 : Vérification du bon fonctionnement ⏱️ 5 minutes

#### 1. Vérifier l'état des services
```bash
docker-compose ps
```

Vous devriez voir quelque chose comme :
```
          Name                        Command               State           Ports
----------------------------------------------------------------------------------------------
llmagents-app         /entrypoint.sh      Up (healthy)   0.0.0.0:8000->8000/tcp
llmagents-qdrant      /usr/local/bin/qdrant Up (healthy)  0.0.0.0:6333->6333/tcp, 0.0.0.0:6334->6334/tcp
llmagents-qdrant-init /bin/sh /init.sh    Exit 0
```

> **⚠️ Si un service n'est pas `Up (healthy)`** : Attendez 1-2 minutes et réessayez. Si le problème persiste, consultez la section [Dépannage](#dépannage).

#### 2. Tester l'API
```bash
# Test simple avec curl
curl http://localhost:8000/api/health

# Devrait retourner un JSON avec le statut du service
```

#### 3. Explorer l'API avec Swagger
Ouvrez votre navigateur et allez sur :
👉 [http://localhost:8000/docs](http://localhost:8000/docs)

Vous verrez la documentation interactive Swagger de votre API avec tous les endpoints disponibles.

#### 4. Vérifier la base de données
Avec `DB_HOST=mysql` (défaut `.env.docker`), la base tourne dans le conteneur `llmagents-mysql` :

```bash
# Lister les tables depuis le conteneur
docker exec -it llmagents-mysql mysql -u $DB_USER -p $DB_NAME

# Dans MySQL :
SHOW TABLES;
DESCRIBE documents;
EXIT;
```

Depuis la machine hôte, un client MySQL peut aussi se connecter sur `localhost:3306`.

Si la base est **externe** (`DB_HOST` ≠ `mysql`), connectez-vous depuis votre machine :

```bash
mysql -h $DB_HOST -P $DB_PORT -u $DB_USER -p $DB_NAME
```

Si des tables manquent, exécutez `docker/mysql/migrate_missing_tables.sql` sur le serveur (fait automatiquement par `import_m3c_dump.sh` en cas d'import).

#### 5. Vérifier Qdrant
```bash
# Tester la connexion à Qdrant
curl http://localhost:6333/readyz

# Devrait retourner {"result":{"ready":true}}

# Voir les collections existantes
curl http://localhost:6333/collections
```

---

### Étape 4 : Utilisation au quotidien ⏱️ 5 minutes

#### Arrêter les services
```bash
# Arrêter tous les conteneurs
docker-compose down
```

#### Redémarrer après modification
```bash
# Si vous avez modifié le code de l'application
docker-compose up -d --build

# Si vous n'avez pas modifié le code (juste les données ou la configuration)
docker-compose up -d
```

#### Voir les logs
```bash
# Voir les logs de tous les services
docker-compose logs -f

# Voir les logs d'un service spécifique
docker-compose logs app
docker-compose logs qdrant

# Voir les 100 dernières lignes
docker-compose logs --tail=100 -f
```

#### Mettre à jour les dépendances
```bash
# Si vous avez modifié requirements-docker.txt
docker-compose build app
docker-compose up -d
```

#### Gérer les données
Vos données sont persistées dans :
- **MySQL** : base externe (hors Docker, sur les serveurs M3C) — sauvegarde à prévoir côté serveur
- **Qdrant** : `/qdrant/storage` (dans le volume Docker `qdrant_data`)
- **Fichiers locaux** : `./rag_sessions`, `./rag_sessions_csv`, `./exports`, etc.

> **💡 Astuce** : Les volumes Docker conservent vos données même après un `docker-compose down`.

---

### Étape 5 : Passage en production (optionnel) ⏱️ 15-30 minutes

#### 1. Sécuriser la configuration
```bash
# Créer un nouveau fichier .env avec des mots de passe forts
# NE JAMAIS committer ce fichier dans Git !

# Exemple de .env sécurisé
DB_PASSWORD=votre_mot_de_passe_complexe_et_long
MISTRAL_API_KEY=votre_clé_api_secrète
REQUIRE_USER_MISTRAL_API_KEY=true
GEMINI_API_KEY=votre_clé_api_google
```

> **Variable `REQUIRE_USER_MISTRAL_API_KEY`** : quand elle vaut `true`
> (défaut), chaque utilisateur normal (rôle `user`/`guest`) doit enregistrer sa
> propre clé API Mistral dans son profil. Mettez `false` pour que la clé du
> serveur (`MISTRAL_API_KEY`), par exemple une clé payante fournie par
> l'administrateur, soit utilisée pour tous les utilisateurs — la clé du serveur
> est alors prioritaire, la clé personnelle servant de repli si la clé serveur
> n'est pas configurée.

> **🔒 Bonne pratique** : Utilisez des mots de passe de 20 caractères minimum avec des caractères spéciaux.

#### 2. Désactiver l'exposition des ports (recommandé)
Dans `docker-compose.yml`, commentez les ports de Qdrant :
```yaml
services:
  qdrant:
    # ports:
    #   - "6333:6333"  # Désactivé pour la production
    #   - "6334:6334"
```

> **⚠️ Important** : En production, les services communiquent via le réseau Docker interne (`llmagents-network`).

#### 3. Configurer les sauvegardes
La base MySQL est externe : utilisez `mysqldump` depuis une machine ayant accès au serveur MySQL (les variables viennent du `.env`) :

```bash
# Exemple de script de sauvegarde (Linux/Mac/WSL)
#!/bin/bash
DATE=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_DIR="./backups"

# Créer le répertoire de sauvegarde
mkdir -p "$BACKUP_DIR"

# Sauvegarder MySQL (base externe)
source .env
mysqldump -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" > "$BACKUP_DIR/backup_${DATE}.sql"
gzip "$BACKUP_DIR/backup_${DATE}.sql"

# Restaurer depuis une sauvegarde
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < backup.sql
```

#### 4. Optimiser les performances
- Allouer plus de mémoire à Docker (minimum **8 Go** recommandé)
- Configurer les ressources dans `docker-compose.yml` :
```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
  qdrant:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G
```

#### 5. Utiliser un fichier de configuration production
Créez un fichier `docker-compose.prod.yml` pour la production :

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  qdrant:
    ports: []  # Aucun port exposé
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G
  
  app:
    ports:
      - "8000:8000"
    environment:
      DB_PASSWORD: ${DB_PASSWORD}
      MISTRAL_API_KEY: ${MISTRAL_API_KEY}
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

Lancez avec :
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 📚 Configuration de référence

### Variables d'environnement

Un fichier `.env.docker` est fourni avec les valeurs par défaut. Vous pouvez :

1. **Pour le développement** : Copier et adapter le fichier
   ```bash
   cp .env.docker .env
   # Modifier .env selon vos besoins
   ```

2. **Pour la production** : Utiliser les valeurs par défaut dans `docker-compose.yml` ou passer des variables via la ligne de commande.

### Configuration de la base de données

Par défaut (`.env.docker`, `DB_HOST=mysql`), la base tourne dans le service Docker `mysql` (conteneur `llmagents-mysql`, volume `mysql_data`, port `3306` publié sur l'hôte). Une base **externe** (serveurs M3C) reste possible en changeant `DB_HOST`.
- L'hôte, le port, le nom, l'utilisateur et le mot de passe sont lus depuis le fichier `.env` (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`).
- Le script `docker/app/entrypoint.sh` attend que MySQL et Qdrant soient joignables avant de démarrer l'application.
- Au premier démarrage du conteneur `mysql` (volume vide), `docker/mysql/init.sql` crée la base, l'utilisateur et les tables du projet.
- Sur une base externe ou après import d'un dump M3C, les tables manquantes sont créées via `docker/mysql/migrate_missing_tables.sql` (automatique avec `import_m3c_dump.sh`).

### 📥 Importer un dump de la base M3C

Si vous disposez d'un dump SQL de la base M3C initiale (sans les tables supplémentaires de ce projet), importez-le dans le MySQL Docker :

```bash
# 1. Démarrer le service MySQL (au premier démarrage, init.sql crée la base et l'utilisateur)
docker compose up -d mysql

# 2. Importer le dump (fichier .sql ou .sql.gz)
./docker/mysql/import_m3c_dump.sh chemin/vers/m3c_dump.sql[.gz]

# 3. Redémarrer l'application pour qu'elle exploite les données
docker compose up -d app
```

Le script `docker/mysql/import_m3c_dump.sh` :
- attend que le conteneur `llmagents-mysql` soit sain ;
- neutralise les instructions `CREATE DATABASE` / `USE` du dump pour importer dans la base `${DB_NAME}` (défaut `m3c_database`) ;
- applique ensuite `docker/mysql/migrate_missing_tables.sql` pour créer les tables/vues spécifiques au projet (idempotent) ;
- affiche la liste des tables à la fin.

#### Importer un gros dump (10 Go et plus)

Le service `mysql` est préconfiguré pour l'import massif (`--disable-log-bin`, `--innodb-flush-log-at-trx-commit=2`, buffer pool 1 Go — à adapter à votre RAM dans `docker-compose.yml`), et le script désactive les checks FK/unique pendant l'import. Comptez de l'ordre de 30 min à quelques heures selon le disque.

```bash
# 0. (Optionnel, recommandé) Adapter le buffer pool à votre RAM dans docker-compose.yml :
#    --innodb-buffer-pool-size=4G   # ou 8G selon la machine

# 1. Démarrer MySQL avec ces options (recrée le conteneur si déjà lancé avec l'ancienne config)
docker compose up -d mysql --force-recreate

# 2. Vérifier que MySQL est sain avant de lancer l'import
docker inspect -f '{{.State.Health.Status}}' llmagents-mysql   # doit afficher : healthy

# 3. Lancer l'import — le dump n'est PAS copié dans le conteneur (pas de docker cp) :
#    il est envoyé par pipe directement au client mysql, donc pas de double
#    occupation disque.
./docker/mysql/import_m3c_dump.sh /chemin/vers/m3c_dump.sql      # ou m3c_dump.sql.gz

# 4. Suivre la progression depuis un autre terminal :

#    a) ce que MySQL est en train de faire (table en cours d'insertion, etc.)
watch docker exec llmagents-mysql mysql -u root -p -e "SHOW PROCESSLIST"

#    b) la taille des données croître dans le volume
watch docker exec llmagents-mysql du -sh /var/lib/mysql

#    c) (Optionnel) barre de progression sur le fichier lui-même : installer pv,
sudo apt install pv
#       puis remplacer `cat "$DUMP_FILE"` par `pv "$DUMP_FILE"` dans docker/mysql/import_m3c_dump.sh

# 5. Une fois l'import terminé (le script affiche la liste des tables) :
docker compose up -d app
```

> **⚠️ Réimport sur base non vide** : les scripts d'init ne s'exécutent que sur un volume vide. Pour repartir d'une base vide avant un nouvel import :
> ```bash
> docker compose down mysql
> docker volume rm m3c-llm_mysql_data   # adapter au nom du projet (docker volume ls pour vérifier)
> docker compose up -d mysql
> ```
>
> ⚠️ Cela supprime définitivement toutes les données MySQL du conteneur.

### Healthchecks

Les services incluent des healthchecks pour s'assurer que :
- Qdrant est accessible avant que l'application ne démarre
- Les collections Qdrant sont créées par le service `qdrant-init` avant que l'application ne démarre

---

## 🎯 Commandes de référence rapide

### Démarrage et arrêt

```bash
# Démarrer tous les services
docker-compose up -d

# Démarrer avec reconstruction (si le code a changé)
docker-compose up -d --build

# Arrêter tous les services
docker-compose down

# Arrêter et supprimer les volumes (ATTENTION : efface les données !)
docker-compose down -v
```

### Inspection et debugging

```bash
# Voir l'état des services
docker-compose ps

# Voir les logs en temps réel
docker-compose logs -f

# Voir les logs d'un service spécifique
docker-compose logs app

# Accéder à la base de données MySQL (externe)
mysql -h $DB_HOST -P $DB_PORT -u $DB_USER -p $DB_NAME

# Exécuter une commande dans le conteneur de l'app
docker exec -it llmagents-app bash
```

### Mise à jour

```bash
# Reconstruire les images
docker-compose build

# Tirer les dernières images de base
docker-compose pull

# Reconstruire et redémarrer
docker-compose up -d --build
```

## 📊 Services disponibles

| Service | Port | Description | URL |
|---------|------|-------------|-----|
| **app** | 8000 | Application FastAPI | [http://localhost:8000](http://localhost:8000) |
| **app** | 8000 | Documentation Swagger | [http://localhost:8000/docs](http://localhost:8000/docs) |
| **qdrant** | 6333 | API HTTP Qdrant | `http://localhost:6333` |
| **qdrant** | 6334 | API gRPC Qdrant | - |
| **qdrant-init** | - | Création des collections Qdrant (one-shot) | - |
| **mysql** | 3306 | Base de données MySQL locale (défaut avec `DB_HOST=mysql`) | `localhost:3306` |
| **MySQL externe** | - | Alternative : base des serveurs M3C | via `DB_HOST` |

---

## 👨‍💻 Développement

### Monter le code en volume (hot-reload)

Pour développer sans reconstruire l'image à chaque modification :

1. Modifiez `docker-compose.yml` pour monter votre code :
```yaml
services:
  app:
    volumes:
      - ./app:/app/app
      - ./config:/app/config
```

2. Activez le reload automatique dans `.env` :
```bash
echo "RELOAD=true" >> .env
```

3. Redémarrez les services :
```bash
docker-compose up -d --build
```

> **💡 Astuce** : Les modifications du code Python seront immédiatement visibles dans le conteneur.

### Outils de développement

```bash
# Se connecter au conteneur de l'application
docker exec -it llmagents-app bash

# Installer des outils supplémentaires dans le conteneur
apt-get update && apt-get install -y vim curl wget

# Voir les fichiers modifiés récemment
find /app -type f -mtime -1
```

### Problèmes connus

| Problème | Solution |
|----------|----------|
| **WindowsSelectorEventLoopPolicy** | Le script `entrypoint.sh` force la politique par défaut pour Linux |
| **Permissions sur Linux** | `chmod +x docker/app/entrypoint.sh` |
| **Port déjà utilisé** | Vérifiez avec `netstat -tuln` ou `lsof -i :8000` |
| **Docker Desktop non démarré** | Démarrez Docker Desktop avant de lancer les conteneurs |

---

## 🏭 Production

### Bonnes pratiques

✅ **Faire** :
- Utiliser des variables d'environnement pour les secrets
- Configurer des limites de ressources (CPU, mémoire)
- Activer les healthchecks (déjà configurés)
- Sauvegarder régulièrement les volumes
- Monitorer les performances

❌ **Ne pas faire** :
- Exposer MySQL et Qdrant sur l'hôte en production
- Utiliser les mots de passe par défaut
- Monter le code en volume (sauf pour le développement)
- Ignorer les logs et métriques

### Configuration recommandée

```yaml
# docker-compose.prod.yml - Exemple de configuration production
version: '3.8'
services:
  app:
    restart: always  # Redémarrage automatique en cas de crash
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
  
  qdrant:
    restart: always
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
```

Lancez avec plusieurs fichiers de configuration :
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Mise à jour

```bash
# Arrêter les services
docker-compose down

# Tirer les dernières images de base
docker-compose pull

# Reconstruire et démarrer
docker-compose up -d --build

# Vérifier les mises à jour disponibles (Linux/Mac)
watch -n 60 docker-compose pull 2>/dev/null && echo "Nouvelles images disponibles"
```

## 🛠️ Dépannage

### 🔍 Diagnostic général

```bash
# Voir l'état détaillé de tous les conteneurs
docker-compose ps -a

# Voir les logs complets
docker-compose logs --tail=200

# Vérifier les ressources utilisées
docker stats

# Inspecter un conteneur spécifique
docker inspect llmagents-app
```

### ❌ Problèmes courants et solutions

#### 1. L'application reste bloquée sur l'attente de MySQL
**Symptômes** : les logs de l'app affichent « MySQL n'est pas encore prêt - attente... » en boucle

**Diagnostic** : la base MySQL est **externe** ; vérifiez qu'elle est joignable depuis votre machine :

```bash
nc -zv $DB_HOST $DB_PORT
```

**Solutions** :
- Vérifiez `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` dans le fichier `.env`
- Vérifiez que le serveur MySQL autorise les connexions depuis votre machine (pare-feu, règles MySQL)
- Vérifiez les identifiants auprès de l'administrateur de la base M3C

#### 2. Qdrant ne démarre pas
**Symptômes** : `llmagents-qdrant` reste en `Starting` ou `Unhealthy`

**Diagnostic** :
```bash
docker logs llmagents-qdrant
```

**Solutions** :
- **Ports 6333/6334 occupés** : Libérez les ports
- **Mémoire insuffisante** : Qdrant a besoin d'au moins 2Go
- **Problème de persistance** : 
  ```bash
  docker volume rm llmagents_qdrant_data
  docker-compose up -d
  ```

#### 3. L'application ne peut pas se connecter à MySQL/Qdrant
**Symptômes** : Erreurs de connexion dans les logs de l'app

**Diagnostic** :
```bash
# Vérifier que les services sont healthy
docker-compose ps

# Tester la connexion manuellement
docker exec -it llmagents-app curl -v http://qdrant:6333
nc -zv $DB_HOST $DB_PORT   # MySQL externe
```

**Solutions** :
- Attendez que les healthchecks passent (`Up (healthy)`)
- Vérifiez les variables d'environnement dans `.env`
- Vérifiez que tous les services sont sur `llmagents-network`
- Pour MySQL (externe), vérifiez que `DB_HOST` est joignable depuis le conteneur

#### 4. Erreur "WindowsSelectorEventLoopPolicy"
**Symptômes** : L'application plante au démarrage avec cette erreur

**Solution** : Déjà gérée par `entrypoint.sh`. Si le problème persiste :
```bash
# Vérifiez que le script a les bonnes permissions
chmod +x docker/app/entrypoint.sh

# Reconstruisez l'image
docker-compose build --no-cache
docker-compose up -d
```

#### 5. L'application ne répond pas sur localhost:8000
**Symptômes** : `Connection refused` ou timeout

**Diagnostic** :
```bash
# Vérifier que le conteneur est démarré
docker ps

# Vérifier les ports exposés
docker port llmagents-app

# Tester depuis l'intérieur du conteneur
docker exec -it llmagents-app curl -v http://localhost:8000/api/health
```

**Solutions** :
- Vérifiez que le port 8000 n'est pas utilisé
- Vérifiez les logs : `docker-compose logs app`
- Attendez que l'application soit prête (peut prendre 1-2 min)

---

## 🔒 Sécurité

### ✅ Checklist de sécurité pour la production

- [ ] **Mots de passe** : Tous les mots de passe par défaut ont été changés
- [ ] **Ports exposés** : Seuls les ports nécessaires sont exposés (généralement uniquement 8000)
- [ ] **Variables d'environnement** : Les secrets sont dans `.env` (pas dans Git)
- [ ] **Sauvegardes** : Un système de sauvegarde des volumes est en place
- [ ] **Mises à jour** : Les images de base sont régulièrement mises à jour
- [ ] **Réseau** : Les services internes ne sont pas exposés sur Internet

### 🛡️ Configuration sécurisée

**Fichier `.env` sécurisé** :
```bash
# Générer des mots de passe forts (20+ caractères)
DB_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9!@#$%^&*()_+' | head -c 24)
MISTRAL_API_KEY=votre_clé_secrète

# Écrire dans .env
echo "DB_PASSWORD=$DB_PASSWORD" > .env
echo "MISTRAL_API_KEY=$MISTRAL_API_KEY" >> .env

# Protéger le fichier
chmod 600 .env
```

**Configuration `docker-compose.yml` sécurisée** :
```yaml
services:
  qdrant:
    ports: []  # Pas de port exposé
    networks:
      - llmagents-network
  
  app:
    ports:
      - "8000:8000"  # Seul le port API est exposé
    environment:
      DB_PASSWORD: ${DB_PASSWORD}
      MISTRAL_API_KEY: ${MISTRAL_API_KEY}
    networks:
      - llmagents-network
```

### 🔥 Sauvegardes automatiques

**Script de sauvegarde quotidien** (Linux/Mac) :
```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y-%m-%d)
BACKUP_DIR="/path/vers/backups/llmagents"
RETENTION=30  # Nombre de jours à conserver

# Créer le répertoire
mkdir -p "$BACKUP_DIR"

# Sauvegarder MySQL (base externe)
echo "Sauvegarde MySQL..."
source .env
mysqldump -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" | gzip > "$BACKUP_DIR/mysql_${DATE}.sql.gz"

# Sauvegarder le volume Qdrant (optionnel)
echo "Sauvegarde volumes..."
docker run --rm -v llmagents_qdrant_data:/qdrant/storage -v "$BACKUP_DIR":/backup alpine tar cvzf /backup/qdrant_data_${DATE}.tar.gz /qdrant/storage

# Nettoyer les anciennes sauvegardes
echo "Nettoyage..."
find "$BACKUP_DIR" -name "*.gz" -mtime +$RETENTION -delete

# Ajouter au cron pour exécuter quotidiennement
# crontab -e
# 0 2 * * * /path/vers/backup.sh
```

## 💾 Structure des données

### Persistance Docker

Les données sont persistées dans des **volumes Docker** :

| Volume | Chemin | Description | Taille estimée |
|--------|--------|-------------|----------------|
| `qdrant_data` | `/qdrant/storage` | Collections et embeddings Qdrant | Variable |

> **💡 Astuce** : Ces volumes conservent vos données même après un `docker-compose down`. La base MySQL est externe et doit être sauvegardée côté serveur.

### Répertoires montés depuis l'hôte

Les répertoires suivants sont **montés depuis votre machine hôte** :

| Répertoire | Description | Persistance |
|------------|-------------|-------------|
| `./rag_sessions` | Sessions RAG (JSON) | ✅ Oui |
| `./rag_sessions_csv` | Sessions RAG au format CSV | ✅ Oui |
| `./session_evaluations` | Évaluations de sessions | ✅ Oui |
| `./temp_pdfs` | Fichiers PDF temporaires | ⚠️ Nettoyer régulièrement |
| `./exports` | Exports de données | ✅ Oui |

> **⚠️ Attention** : Les fichiers dans ces répertoires sont accessibles directement depuis votre machine et depuis le conteneur.

### Schéma de stockage

```
Votre machine
├── LLMAgents/
│   ├── rag_sessions/          → /app/rag_sessions/ (dans conteneur)
│   ├── rag_sessions_csv/      → /app/rag_sessions_csv/
│   ├── session_evaluations/   → /app/session_evaluations/
│   ├── temp_pdfs/             → /app/temp_pdfs/
│   └── exports/                → /app/exports/
└── Volumes Docker
    └── qdrant_data/            → /qdrant/storage (Qdrant)

La base MySQL est externe (hors Docker) : elle n'apparaît pas ici.
```

### Sauvegarde recommandée

Pour une sauvegarde complète :
1. **Volumes Docker** : Utilisez `docker volume` ou sauvegardez via les conteneurs
2. **Répertoires locaux** : Copiez simplement les dossiers `rag_sessions`, `exports`, etc.
3. **Base de données** : Utilisez `mysqldump` comme montré dans la section [Sauvegardes](#-sauvegardes-automatiques)
