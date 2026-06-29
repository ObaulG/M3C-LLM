-- V002: Table des jobs d'indexation

CREATE TABLE IF NOT EXISTS indexing_jobs (
    job_id VARCHAR(36) PRIMARY KEY COMMENT 'UUID du job',
    job_type VARCHAR(50) NOT NULL DEFAULT 'pdf-indexing' COMMENT 'Type de job',
    status ENUM('pending','running','paused','completed','failed','cancelled') NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    total_items INT NOT NULL,
    processed_items INT NOT NULL DEFAULT 0,
    progress JSON COMMENT 'Progression détaillée par resource_id',
    parameters JSON COMMENT 'Paramètres du job',
    error_message TEXT COMMENT 'Message d\'erreur si échec',
    INDEX idx_job_type_status (job_type, status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
