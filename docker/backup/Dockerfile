# Image de sauvegarde LLMAgents : mysqldump (image MySQL) + curl pour Qdrant
FROM mysql:8.0

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backup.sh /usr/local/bin/backup.sh
COPY restore.sh /usr/local/bin/restore.sh
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/restore.sh

WORKDIR /workspace
ENTRYPOINT ["backup.sh"]
