#!/bin/sh
# =============================================================================
# Script de restauration locale pour LLMAgents
# =============================================================================
# Restaure une sauvegarde créée par docker/backup/backup.sh :
#   1. Les tables MySQL depuis le dump gzippé
#   2. Les collections Qdrant depuis les fichiers .snapshot
#
# Utilisation (depuis la racine du projet) :
#   docker compose --profile backup run --rm backup restore.sh backups/backup_<DATE>
#
# Ou directement (machine hôte disposant de mysql et curl) :
#   BACKUP_DIR=./backups ./docker/backup/restore.sh backup_<DATE>
# =============================================================================

set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"

DB_HOST="${DB_HOST:-mysql}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-m3c_database}"
DB_USER="${DB_USER:-OBL}"
DB_PASSWORD="${DB_PASSWORD:-azerty}"

QDRANT_HOST="${QDRANT_HOST:-qdrant}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
QDRANT_URL="http://${QDRANT_HOST}:${QDRANT_PORT}"

if [ "$#" -ne 1 ]; then
    echo "Usage : $0 <nom_du_backup>   (ex : backup_2024-01-31_02-00-00)"
    echo "Sauvegardes disponibles dans ${BACKUP_DIR} :"
    ls -1 "${BACKUP_DIR}" 2>/dev/null || true
    exit 1
fi

TARGET_DIR="${BACKUP_DIR}/$1"

if [ ! -d "${TARGET_DIR}" ]; then
    echo "ERREUR : sauvegarde introuvable : ${TARGET_DIR}"
    exit 1
fi

echo "=== Restauration LLMAgents depuis ${TARGET_DIR} ==="

# -----------------------------------------------------------------------------
# 1. MySQL
# -----------------------------------------------------------------------------
MYSQL_DUMP="$(ls "${TARGET_DIR}"/mysql_*.sql.gz 2>/dev/null | head -n 1 || true)"

if [ -n "${MYSQL_DUMP}" ]; then
    echo ""
    echo "--- MySQL : restauration de ${MYSQL_DUMP} dans ${DB_NAME} ---"
    gunzip -c "${MYSQL_DUMP}" | mysql -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -p"${DB_PASSWORD}" "${DB_NAME}"
    echo "OK : tables MySQL restaurées."
else
    echo "Aucun dump MySQL trouvé dans la sauvegarde."
fi

# -----------------------------------------------------------------------------
# 2. Qdrant
# -----------------------------------------------------------------------------
echo ""
echo "--- Qdrant : restauration des collections ---"

i=0
while [ "$i" -lt 30 ]; do
    curl -sf "${QDRANT_URL}/readyz" >/dev/null 2>&1 && break
    i=$((i + 1))
    sleep 2
done
if ! curl -sf "${QDRANT_URL}/readyz" >/dev/null 2>&1; then
    echo "ERREUR : Qdrant n'est pas disponible sur ${QDRANT_URL}"
    exit 1
fi

SNAPSHOTS="$(ls "${TARGET_DIR}"/*.snapshot 2>/dev/null || true)"

if [ -z "${SNAPSHOTS}" ]; then
    echo "Aucun snapshot Qdrant trouvé dans la sauvegarde."
else
    for SNAPSHOT in ${SNAPSHOTS}; do
        COLLECTION="$(basename "${SNAPSHOT}" | sed 's/^qdrant_//; s/_[0-9-]*_[0-9-]*\.snapshot$//')"
        echo "Collection : ${COLLECTION} (depuis $(basename "${SNAPSHOT}"))"

        # "upload" crée la collection si elle n'existe pas ; sinon on bascule
        # sur "recover" qui écrase les données de la collection existante.
        if ! curl -sf -X PUT \
            "${QDRANT_URL}/collections/${COLLECTION}/snapshots/upload?wait=true" \
            -F "snapshot=@${SNAPSHOT}" > /dev/null; then
            curl -sf -X PUT \
                "${QDRANT_URL}/collections/${COLLECTION}/snapshots/recover?wait=true&priority=snapshot" \
                -F "snapshot=@${SNAPSHOT}" > /dev/null
        fi
        echo "OK : collection ${COLLECTION} restaurée."
    done
fi

echo ""
echo "=== Restauration terminée ==="
