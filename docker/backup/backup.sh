#!/bin/sh
# =============================================================================
# Script de sauvegarde locale pour LLMAgents
# =============================================================================
# Sauvegarde :
#   1. Les tables MySQL décrites dans docker/mysql/init.sql (uniquement
#      celles-ci, via mysqldump --tables)
#   2. Les collections Qdrant (snapshots créés via l'API puis téléchargés)
#
# Les sauvegardes sont écrites dans BACKUP_DIR (défaut : /backups, monté
# sur ./backups dans docker-compose.yml). Les sauvegardes plus anciennes
# que RETENTION_DAYS jours sont supprimées.
#
# Utilisation (depuis la racine du projet) :
#   docker compose --profile backup run --rm backup
#
# Ou directement (machine hôte disposant de mysqldump et curl) :
#   DB_HOST=localhost QDRANT_HOST=localhost ./docker/backup/backup.sh
# =============================================================================

set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
INIT_SQL="${INIT_SQL:-/init.sql}"

DB_HOST="${DB_HOST:-mysql}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-m3c_database}"
DB_USER="${DB_USER:-OBL}"
DB_PASSWORD="${DB_PASSWORD:-azerty}"

QDRANT_HOST="${QDRANT_HOST:-qdrant}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
QDRANT_URL="http://${QDRANT_HOST}:${QDRANT_PORT}"

DATE="$(date +%Y-%m-%d_%H-%M-%S)"
TARGET_DIR="${BACKUP_DIR}/backup_${DATE}"

echo "=== Sauvegarde LLMAgents - ${DATE} ==="
echo "Cible MySQL : ${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo "Cible Qdrant : ${QDRANT_URL}"
echo "Destination : ${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"

# -----------------------------------------------------------------------------
# 1. MySQL : uniquement les tables définies dans le fichier SQL d'init
# -----------------------------------------------------------------------------
if [ ! -f "${INIT_SQL}" ]; then
    echo "ERREUR : fichier SQL introuvable : ${INIT_SQL}"
    exit 1
fi

# Extraction des noms de tables depuis les CREATE TABLE du script SQL.
TABLES="$(sed -n 's/^CREATE TABLE IF NOT EXISTS `\?\([A-Za-z0-9_]*\)`\?.*$/\1/p' "${INIT_SQL}")"
TABLE_COUNT="$(echo "${TABLES}" | grep -c . || true)"

if [ "${TABLE_COUNT}" -eq 0 ]; then
    echo "ERREUR : aucune table trouvée dans ${INIT_SQL}"
    exit 1
fi

echo ""
echo "--- MySQL : sauvegarde de ${TABLE_COUNT} tables ---"
echo "${TABLES}" | tr '\n' ' ' > "${TARGET_DIR}/tables.txt"

MYSQLDUMP_ARGS="-h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD}"
# shellcheck disable=SC2086
mysqldump ${MYSQLDUMP_ARGS} \
    --single-transaction --quick --routines --triggers \
    "${DB_NAME}" ${TABLES} | gzip > "${TARGET_DIR}/mysql_${DB_NAME}_${DATE}.sql.gz"

echo "OK : ${TARGET_DIR}/mysql_${DB_NAME}_${DATE}.sql.gz"

# -----------------------------------------------------------------------------
# 2. Qdrant : snapshot de chaque collection, puis téléchargement
# -----------------------------------------------------------------------------
echo ""
echo "--- Qdrant : sauvegarde des collections ---"

wait_for_qdrant() {
    i=0
    while [ "$i" -lt 30 ]; do
        if curl -sf "${QDRANT_URL}/readyz" >/dev/null 2>&1; then
            return 0
        fi
        i=$((i + 1))
        sleep 2
    done
    echo "ERREUR : Qdrant n'est pas disponible sur ${QDRANT_URL}"
    return 1
}

wait_for_qdrant

COLLECTIONS="$(curl -sf "${QDRANT_URL}/collections" | sed 's/.*"collections":\[\([^]]*\)\].*/\1/' | tr ',' '\n' | sed 's/"//g' | sed '/^$/d')"

if [ -z "${COLLECTIONS}" ]; then
    echo "Aucune collection Qdrant à sauvegarder."
else
    echo "${COLLECTIONS}" > "${TARGET_DIR}/qdrant_collections.txt"
    for COLLECTION in ${COLLECTIONS}; do
        echo "Collection : ${COLLECTION}"
        SNAPSHOT_NAME="backup_${DATE}"
        curl -sf -X POST \
            "${QDRANT_URL}/collections/${COLLECTION}/snapshots?wait=true" \
            -H 'Content-Type: application/json' \
            -d "{\"name\": \"${SNAPSHOT_NAME}\"}" > /dev/null

        curl -sf -o "${TARGET_DIR}/qdrant_${COLLECTION}_${DATE}.snapshot" \
            "${QDRANT_URL}/collections/${COLLECTION}/snapshots/${SNAPSHOT_NAME}"

        # Supprimer le snapshot côté serveur pour ne pas gonfler le stockage Qdrant
        curl -sf -X DELETE \
            "${QDRANT_URL}/collections/${COLLECTION}/snapshots/${SNAPSHOT_NAME}" > /dev/null || true

        echo "OK : ${TARGET_DIR}/qdrant_${COLLECTION}_${DATE}.snapshot"
    done
fi

# -----------------------------------------------------------------------------
# 3. Manifeste et rétention
# -----------------------------------------------------------------------------
cat > "${TARGET_DIR}/manifest.txt" <<EOF
date=${DATE}
db_name=${DB_NAME}
db_host=${DB_HOST}
qdrant_host=${QDRANT_HOST}
tables=${TABLE_COUNT}
EOF

echo ""
echo "--- Nettoyage : suppression des sauvegardes de plus de ${RETENTION_DAYS} jours ---"
find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d -name 'backup_*' -mtime "+${RETENTION_DAYS}" -exec rm -rf {} + 2>/dev/null || true

echo ""
echo "=== Sauvegarde terminée : ${TARGET_DIR} ==="
