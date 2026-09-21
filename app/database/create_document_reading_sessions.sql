-- Script SQL pour créer la table d'observation de lecture de documents
-- À exécuter dans la base de données MySQL (m3c_database)
--
-- Chaque ouverture d'un PDF dans m3c-chatbot.html crée une ligne avec
-- opened_at ; la fermeture (bouton, changement de document, départ de la page)
-- complète closed_at, close_reason et duration_seconds.

CREATE TABLE IF NOT EXISTS document_reading_sessions (
    reading_session_id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Identifiant unique de la session de lecture',
    user_id VARCHAR(100) NOT NULL COMMENT 'Identifiant de l\'utilisateur (user:<id> si connecté, anonymous:<uuid> sinon)',
    resource_id INT NOT NULL COMMENT 'resource_id (table value) du document PDF ouvert',
    num_page INT NULL COMMENT 'Numéro de page ciblé à l\'ouverture, si fourni',
    opened_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp d\'ouverture du document',
    closed_at TIMESTAMP NULL COMMENT 'Timestamp de fermeture du document',
    close_reason ENUM('button', 'document_change', 'page_hide') NULL COMMENT 'Événement ayant déclenché la fermeture',
    duration_seconds INT NULL COMMENT 'Durée de lecture en secondes, calculée à la fermeture',
    metadata JSON COMMENT 'Métadonnées supplémentaires (session RAG, page, etc.)',
    INDEX idx_drs_user (user_id),
    INDEX idx_drs_resource (resource_id),
    INDEX idx_drs_opened_at (opened_at),
    INDEX idx_drs_user_opened (user_id, opened_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Vérification: afficher la structure de la table
SHOW CREATE TABLE document_reading_sessions;
