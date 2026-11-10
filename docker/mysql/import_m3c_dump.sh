#!/usr/bin/env bash
# =============================================================================
# IMPORT D'UN DUMP SQL DE LA BASE M3C INITIALE DANS LE MYSQL DOCKER
# =============================================================================
# Usage :
#   ./docker/mysql/import_m3c_dump.sh <chemin/vers/dump.sql | dump.sql.gz>
#
# Ce script :
#   1. attend que le service MySQL Docker (llmagents-mysql) soit sain ;
#   2. neutralise les instructions CREATE DATABASE / USE du dump afin que
#      les données soient importées dans la base ${DB_NAME:-m3c_database} ;
#   3. importe le dump dans cette base ;
#   4. applique docker/mysql/migrate_missing_tables.sql pour créer les
#      tables/vues spécifiques à ce projet (idempotent).
#
# Prérequis :
#   - docker compose up -d mysql (le service mysql de docker-compose.yml) ;
#   - un dump SQL de la base M3C initiale, éventuellement compressé (.gz).
#
# Remarques :
#   - Le dump ne doit pas contenir les tables spécifiques à ce projet
#     (elles sont créées par migrate_missing_tables.sql) ;
#   - Pour repartir d'une base vide avant l'import :
#       docker compose stop mysql && docker volume rm <projet>_mysql_data
# =============================================================================

set -euo pipefail

# Se placer à la racine du projet (là où se trouve docker-compose.yml)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Charger DB_NAME / DB_USER / DB_PASSWORD depuis .env si présent
if [ -f .env ]; then
    # shellcheck disable=SC1091
    set -a; . ./.env; set +a
fi
DB_NAME="${DB_NAME:-m3c_database}"
DB_USER="${DB_USER:-OBL}"
DB_PASSWORD="${DB_PASSWORD:-azerty}"
CONTAINER="llmagents-mysql"

if [ $# -ne 1 ]; then
    echo "Usage : $0 <chemin/vers/dump.sql | dump.sql.gz>" >&2
    exit 1
fi

DUMP_FILE="$1"
if [ ! -f "$DUMP_FILE" ]; then
    echo "Erreur : fichier introuvable : $DUMP_FILE" >&2
    exit 1
fi

# Vérifier que le conteneur MySQL tourne
if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
    echo "Erreur : le conteneur $CONTAINER n'est pas en cours d'exécution." >&2
    echo "Lancez d'abord : docker compose up -d mysql" >&2
    exit 1
fi

# Attendre que MySQL soit sain (healthcheck docker-compose.yml)
echo "Attente de la disponibilité de MySQL..."
TIMEOUT=120
ELAPSED=0
until [ "$(docker inspect -f '{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null)" = "healthy" ]; do
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo "Erreur : MySQL n'est pas devenu sain en ${TIMEOUT}s." >&2
        exit 1
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

# Lecteur de dump : décompression gzip transparente
read_dump() {
    case "$DUMP_FILE" in
        *.gz) gunzip -c "$DUMP_FILE" ;;
        *)    cat "$DUMP_FILE" ;;
    esac
}

# Neutraliser CREATE/DROP DATABASE et USE (le dump peut viser une autre base)
# et retirer les clauses DEFINER (elles requierent le privilege SUPER sinon)
strip_dump() {
    sed -E \
        -e 's/^([[:space:]]*)(CREATE[[:space:]]+DATABASE|DROP[[:space:]]+DATABASE|USE)[[:space:]]+.*/\1-- [import_m3c_dump] instruction ignoree: &/I' \
        -e 's/DEFINER=`[^`]*`@`[^`]*` ?//g' \
        -e 's/DEFINER=[^ ]+ ?//g'
}

# Desactiver les checks FK/unique pendant l'import (gros gains sur les gros dumps)
MYSQL_INIT_CMD="SET SESSION foreign_key_checks=0; SET SESSION unique_checks=0;"

echo "Import de \"$DUMP_FILE\" dans la base \"$DB_NAME\" (conteneur $CONTAINER)..."
echo "(dump volumineux : l'operation peut durer longtemps ; suivez la progression"
echo " depuis un autre terminal avec :"
echo "  watch docker exec $CONTAINER mysql -u root -p\"\$MYSQL_ROOT_PASSWORD\" -e \"SHOW PROCESSLIST\" )"
read_dump "$DUMP_FILE" | strip_dump \
    | docker exec -i -e MYSQL_PWD="$DB_PASSWORD" "$CONTAINER" \
        mysql --binary-mode --init-command="$MYSQL_INIT_CMD" -u "$DB_USER" "$DB_NAME"

echo "Création des tables/vues spécifiques au projet (migrate_missing_tables.sql)..."
docker exec -i -e MYSQL_PWD="$DB_PASSWORD" "$CONTAINER" \
    mysql --binary-mode -u "$DB_USER" "$DB_NAME" \
    < docker/mysql/migrate_missing_tables.sql

echo "Import terminé. Tables présentes dans \"$DB_NAME\" :"
docker exec -e MYSQL_PWD="$DB_PASSWORD" "$CONTAINER" \
    mysql -u "$DB_USER" "$DB_NAME" -e "SHOW TABLES;"
