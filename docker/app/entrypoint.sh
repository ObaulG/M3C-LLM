#!/bin/bash
set -e

# Script d'entrée pour l'application LLMAgents
# Ce script est exécuté au démarrage du conteneur

echo "=========================================="
echo "Démarrage de l'application LLMAgents"
echo "=========================================="

# Attendre que les dépendances soient prêtes
echo "Attente de la disponibilité de MySQL..."
until nc -z -v -w30 mysql 3306; do
  echo "MySQL n'est pas encore prêt - attente..."
  sleep 5
done
echo "MySQL est disponible !"

echo "Attente de la disponibilité de Qdrant..."
until nc -z -v -w30 qdrant 6333; do
  echo "Qdrant n'est pas encore prêt - attente..."
  sleep 5
done
echo "Qdrant est disponible !"

# Définir la politique d'event loop pour Linux (évite le problème WindowsSelectorEventLoopPolicy)
export PYTHONASYNCIODEBUG=0

# Afficher les variables d'environnement pour le débogage
echo ""
echo "Variables d'environnement :"
echo "DB_HOST: ${DB_HOST}"
echo "DB_PORT: ${DB_PORT}"
echo "DB_NAME: ${DB_NAME}"
echo "DB_USER: ${DB_USER}"
echo "QDRANT_HOST: ${QDRANT_HOST}"
echo "QDRANT_PORT: ${QDRANT_PORT}"
echo "API_HOST: ${API_HOST}"
echo "API_PORT: ${API_PORT}"
echo ""

# Démarrer l'application avec uvicorn
# On force la politique d'event loop par défaut pour éviter les problèmes Windows
exec python -c "
import asyncio
import os
import sys

# Forcer la politique d'event loop par défaut pour Linux
asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

# Importer et démarrer l'application
from app.api_server import app
import uvicorn

host = os.getenv('API_HOST', '0.0.0.0')
port = int(os.getenv('API_PORT', '8000'))

print(f'Démarrage du serveur sur {host}:{port}')
print(f'Documentation disponible sur http://{host}:{port}/docs')

uvicorn.run(
    'app.api_server:app',
    host=host,
    port=port,
    reload=False,
    log_level='info',
    loop='asyncio'
)
"
