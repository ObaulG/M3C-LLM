-- Script SQL pour créer la table de gestion des jobs d'indexation
-- À exécuter dans la base de données MySQL (m3c_database)

CREATE TABLE IF NOT EXISTS indexing_jobs (
    job_id VARCHAR(36) PRIMARY KEY COMMENT 'Identifiant unique du job (UUID)',
    job_type VARCHAR(50) NOT NULL DEFAULT 'pdf-indexing' COMMENT 'Type de job (ex: pdf-from-m3c)',
    status ENUM('pending', 'running', 'paused', 'completed', 'failed', 'cancelled') NOT NULL DEFAULT 'pending' COMMENT 'Statut actuel du job',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Date de création du job',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Dernière mise à jour du job',
    total_items INT NOT NULL COMMENT 'Nombre total d\'éléments à traiter',
    processed_items INT NOT NULL DEFAULT 0 COMMENT 'Nombre d\'éléments déjà traités',
    progress JSON COMMENT 'Progression détaillée par resource_id: {"resource_id": {"status": "completed", "chunks_count": 5, "error": null, "processed_at": "..."}}',
    parameters JSON COMMENT 'Paramètres du job: {"chunk_size": 2700, "chunk_overlap": 400}',
    error_message TEXT COMMENT 'Message d\'erreur si le job a échoué'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Index pour optimiser les requêtes de filtrage
CREATE INDEX IF NOT EXISTS idx_indexing_jobs_type_status ON indexing_jobs(job_type, status);
CREATE INDEX IF NOT EXISTS idx_indexing_jobs_created ON indexing_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_indexing_jobs_job_id ON indexing_jobs(job_id);

-- Vérification: afficher la structure de la table
SHOW CREATE TABLE indexing_jobs;
