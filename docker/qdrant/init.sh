#!/bin/sh
# =============================================================================
# Script d'initialisation des collections Qdrant pour LLMAgents
# =============================================================================
# Ce script crée les collections Qdrant nécessaires au fonctionnement de
# l'application au démarrage du conteneur, sur le même principe que
# docker/mysql/init.sql pour MySQL.
#
# Il est conçu pour être exécuté après que le service Qdrant soit disponible.
# Les collections sont créées avec "create_collection" si elles n'existent pas
# déjà (PUT /collections/{name} est idempotent : il ne fait rien si la
# collection existe déjà avec les mêmes paramètres).
#
# Conventions de nommage des collections :
#   LD-{model_name}-{dimension}  -> chunks de texte (Long Document)
#   MD-{model_name}-{dimension}  -> métadonnées (Metadata Document)
#
# Utilisation :
#   ./docker/qdrant/init.sh [QDRANT_HOST] [QDRANT_PORT]
#
# Par défaut : QDRANT_HOST=localhost, QDRANT_PORT=6333
# =============================================================================

set -e

QDRANT_HOST="${1:-${QDRANT_HOST:-localhost}}"
QDRANT_PORT="${2:-${QDRANT_PORT:-6333}}"
QDRANT_URL="http://${QDRANT_HOST}:${QDRANT_PORT}"

echo "=========================================="
echo "Initialisation des collections Qdrant"
echo "=========================================="
echo "Cible : ${QDRANT_URL}"
echo ""

# ----------------------------------------------------------------------------
# Fonction : attendre que Qdrant soit disponible
# ----------------------------------------------------------------------------
wait_for_qdrant() {
    echo "Attente de la disponibilité de Qdrant..."
    MAX_RETRIES=30
    RETRY=0
    while [ $RETRY -lt $MAX_RETRIES ]; do
        if curl -sf "${QDRANT_URL}/readyz" >/dev/null 2>&1; then
            echo "Qdrant est disponible !"
            return 0
        fi
        RETRY=$((RETRY + 1))
        echo "  Qdrant non pret (tentative ${RETRY}/${MAX_RETRIES})..."
        sleep 2
    done
    echo "ERREUR : Qdrant n'est pas disponible apres ${MAX_RETRIES} tentatives."
    exit 1
}

# ----------------------------------------------------------------------------
# Fonction : creer une collection si elle n'existe pas
# Arguments :
#   $1 : nom de la collection
#   $2 : dimension des vecteurs
#   $3 : distance (Cosine, Dot, Euclid) - par defaut Cosine
# ----------------------------------------------------------------------------
create_collection() {
    COLLECTION_NAME="$1"
    VECTOR_SIZE="$2"
    DISTANCE="${3:-Cosine}"

    echo "Verification de la collection '${COLLECTION_NAME}'..."

    # Verifier si la collection existe deja
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
        "${QDRANT_URL}/collections/${COLLECTION_NAME}")

    if [ "$HTTP_STATUS" = "200" ]; then
        echo "  -> Collection '${COLLECTION_NAME}' existe deja, ignore."
        return 0
    fi

    echo "  -> Creation de la collection '${COLLECTION_NAME}' (dim=${VECTOR_SIZE}, distance=${DISTANCE})..."

    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
        -X PUT "${QDRANT_URL}/collections/${COLLECTION_NAME}" \
        -H "Content-Type: application/json" \
        -d "{
            \"vectors\": {
                \"size\": ${VECTOR_SIZE},
                \"distance\": \"${DISTANCE}\"
            }
        }")

    if [ "$HTTP_STATUS" = "200" ]; then
        echo "  -> Collection '${COLLECTION_NAME}' creee avec succes."
    else
        echo "  -> ERREUR : echec de la creation de '${COLLECTION_NAME}' (HTTP ${HTTP_STATUS})."
        return 1
    fi
}

# ----------------------------------------------------------------------------
# Fonction : afficher le resume des collections existantes
# ----------------------------------------------------------------------------
list_collections() {
    echo ""
    echo "Collections Qdrant actuelles :"
    COLLECTIONS=$(curl -sf "${QDRANT_URL}/collections" 2>/dev/null)
    if [ -n "$COLLECTIONS" ]; then
        echo "$COLLECTIONS" | sed 's/^/  /'
    else
        echo "  (impossible de recuperer la liste)"
    fi
}

# ============================================================================
# EXECUTION
# ============================================================================

wait_for_qdrant
echo ""

# --- Collection principale : chunks de texte (mistral-embed, 1024 dim) -----
# Utilisee par api_server.py, api_visualization.py, rag_pipeline.py,
# question_answer/generation_services.py
create_collection "LD-mistral-mistral-embed-1024" 1024 Cosine

# --- Collection pour les métadonnées (mistral-embed, 1024 dim) -------------
# Utilisee par indexing/services.py pour les embeddings de métadonnées
create_collection "MD-mistral-mistral-embed-1024" 1024 Cosine

list_collections

echo ""
echo "=========================================="
echo "Initialisation Qdrant terminee"
echo "=========================================="
