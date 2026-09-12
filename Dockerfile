# Dockerfile optimisé pour l'application LLMAgents
# Utilisation d'un multi-stage build pour réduire la taille de l'image finale

# ============================================================================
# STAGE 1: Build - Installation des dépendances
# ============================================================================
FROM python:3.12-slim as builder

# Définir les variables d'environnement pour le build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# Installer les dépendances système nécessaires pour la compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmariadb-dev \
    libmariadb-dev-compat \
    gcc \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copier uniquement les fichiers nécessaires pour l'installation des dépendances
COPY requirements-docker.txt requirements.txt

# Installer les dépendances Python dans un répertoire temporaire
RUN pip install --user --no-cache-dir -r requirements.txt

# ============================================================================
# STAGE 2: Runtime - Image finale légère
# ============================================================================
FROM python:3.12-slim as runtime

# Définir les variables d'environnement pour l'exécution
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PYTHONASYNCIODEBUG=0

WORKDIR /app

# Installer les dépendances système minimales pour l'exécution
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmariadb3 \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copier les dépendances Python depuis le stage builder
COPY --from=builder /root/.local /root/.local

# Rendre les scripts Python dans .local utilisables
ENV PATH=/root/.local/bin:$PATH

# Copier le code source de l'application
COPY app/ ./app/
COPY config/ ./config/
COPY docker/app/entrypoint.sh /entrypoint.sh

# Copier le fichier .env.example pour référence
COPY .env.example .

# Créer les répertoires nécessaires pour les données persistantes
RUN mkdir -p /app/data \
    && mkdir -p /app/rag_sessions \
    && mkdir -p /app/rag_sessions_csv \
    && mkdir -p /app/session_evaluations \
    && mkdir -p /app/temp_pdfs \
    && mkdir -p /app/exports

# Donner les permissions d'exécution au script d'entrée
RUN chmod +x /entrypoint.sh

# Exposer le port de l'application
EXPOSE 8000

# Utiliser le script d'entrée personnalisé
ENTRYPOINT ["/entrypoint.sh"]
