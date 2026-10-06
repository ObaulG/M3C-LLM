-- Script d'initialisation de la base de données MySQL pour LLMAgents
-- Ce script est exécuté automatiquement au premier démarrage du conteneur MySQL
-- Compatible avec MySQL 8.0+

-- Arrêter en cas d'erreur
SET SQL_MODE = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION';

-- Créer la base de données si elle n'existe pas
CREATE DATABASE IF NOT EXISTS m3c_database CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE m3c_database;

-- Créer l'utilisateur et lui donner les droits sur la base
CREATE USER IF NOT EXISTS 'OBL'@'%' IDENTIFIED BY 'azerty';
GRANT ALL PRIVILEGES ON m3c_database.* TO 'OBL'@'%';
GRANT ALL PRIVILEGES ON m3c_database.* TO 'OBL'@'localhost';
FLUSH PRIVILEGES;

-- =============================================================================
-- TABLES PRINCIPALES
-- =============================================================================

-- Table pour les documents
CREATE TABLE IF NOT EXISTS documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    title VARCHAR(500),
    author VARCHAR(500),
    source_type VARCHAR(50) DEFAULT 'pdf',
    source_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_document_source (source_type, source_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table pour les chunks de documents (texte extrait)
CREATE TABLE IF NOT EXISTS text_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL DEFAULT 'pdf',
    source_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_text_document_source (source_type, source_id),
    INDEX idx_source_type (source_type),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table pour les stratégies de chunking
CREATE TABLE IF NOT EXISTS text_chunking_strategies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    method VARCHAR(50) NOT NULL,
    chunk_size INT,
    char_size INT,
    overlap INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_strategy_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table pour les chunks de texte
CREATE TABLE IF NOT EXISTS text_chunks (
    id VARCHAR(255) PRIMARY KEY,
    document_id INT NOT NULL,
    strategy_id INT NOT NULL,
    content TEXT NOT NULL,
    num_page INT,
    position_in_page INT,
    token_count INT,
    character_count INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES text_documents(id) ON DELETE CASCADE,
    FOREIGN KEY (strategy_id) REFERENCES text_chunking_strategies(id) ON DELETE CASCADE,
    INDEX idx_chunk_document (document_id),
    INDEX idx_chunk_strategy (strategy_id),
    FULLTEXT INDEX ft_chunk_content (content)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================================================================
-- TABLES POUR LES QUESTIONS
-- =============================================================================

-- Table pour les questions
CREATE TABLE IF NOT EXISTS questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    resource_id INT,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES text_documents(id) ON DELETE CASCADE,
    INDEX idx_question_document (document_id),
    INDEX idx_question_resource (resource_id),
    FULLTEXT INDEX ft_question_content (content)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table pour les réponses aux questions
CREATE TABLE IF NOT EXISTS answers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    question_id INT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    INDEX idx_answer_question (question_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================================================================
-- TABLES POUR LES SESSIONS
-- =============================================================================

-- Table pour les sessions
CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR(36) PRIMARY KEY,
    document_id INT,
    user_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES text_documents(id) ON DELETE CASCADE,
    INDEX idx_session_document (document_id),
    INDEX idx_session_user (user_id),
    INDEX idx_session_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table pour les messages de session (questions/réponses)
CREATE TABLE IF NOT EXISTS session_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    question_id INT,
    role ENUM('user', 'assistant', 'system') NOT NULL,
    content TEXT NOT NULL,
    message_type VARCHAR(50),
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE SET NULL,
    INDEX idx_session_message_session (session_id),
    INDEX idx_session_message_question (question_id),
    INDEX idx_session_message_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================================================================
-- TABLES POUR L'INDEXATION
-- =============================================================================

-- Table pour les jobs d'indexation
CREATE TABLE IF NOT EXISTS indexing_jobs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES text_documents(id) ON DELETE CASCADE,
    INDEX idx_indexing_job_document (document_id),
    INDEX idx_indexing_job_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================================================================
-- TABLES POUR LE RAG (Retrieval-Augmented Generation)
-- =============================================================================

-- Table pour les embeddings stockés dans Qdrant (références)
CREATE TABLE IF NOT EXISTS chunk_embeddings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    chunk_id VARCHAR(255) NOT NULL,
    document_id INT NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    collection_name VARCHAR(100),
    vector_size INT,
    qdrant_point_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_chunk_embedding (chunk_id, model_name),
    FOREIGN KEY (document_id) REFERENCES text_documents(id) ON DELETE CASCADE,
    INDEX idx_chunk_embedding_chunk (chunk_id),
    INDEX idx_chunk_embedding_model (model_name),
    INDEX idx_chunk_embedding_document (document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table pour les évaluations des réponses
CREATE TABLE IF NOT EXISTS evaluations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(36),
    question_id INT,
    model_used VARCHAR(100),
    score DECIMAL(5,2),
    feedback TEXT,
    evaluation_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE SET NULL,
    INDEX idx_evaluation_session (session_id),
    INDEX idx_evaluation_question (question_id),
    INDEX idx_evaluation_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================================================================
-- TABLES DE VALIDATION DU CHUNKING
-- (source : app/database/sql_tables_scripts/chunks.sql)
-- =============================================================================

-- Table de validation du découpage par document et stratégie
CREATE TABLE IF NOT EXISTS text_document_chunking_validation (
    document_id INT NOT NULL,
    strategy_id INT NOT NULL,
    chunks_nb INT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES text_documents(id) ON DELETE CASCADE,
    FOREIGN KEY (strategy_id) REFERENCES text_chunking_strategies(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================================================================
-- TABLES D'OBSERVATION DE LECTURE
-- (source : app/database/sql_tables_scripts/create_document_reading_sessions.sql)
-- =============================================================================

-- Table d'observation des sessions de lecture de documents
-- Remarque : la clé étrangère vers user(id) du script original est omise,
-- la table user n'étant pas créée ici (script PostgreSQL non inclus).
CREATE TABLE IF NOT EXISTS document_reading_sessions (
    reading_session_id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Identifiant unique de la session de lecture',
    user_id INT NULL COMMENT 'user_id de la table users si connecté, NULL pour un visiteur anonyme',
    anonymous_id VARCHAR(100) NULL COMMENT 'Identifiant anonyme persistant (localStorage) si non connecté',
    resource_id INT NOT NULL COMMENT 'resource_id (table value) du document PDF ouvert',
    num_page INT NULL COMMENT 'Numéro de page ciblé à l''ouverture, si fourni',
    opened_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp d''ouverture du document',
    closed_at TIMESTAMP NULL COMMENT 'Timestamp de fermeture du document',
    close_reason ENUM('button', 'document_change', 'page_hide') NULL COMMENT 'Événement ayant déclenché la fermeture',
    duration_seconds INT NULL COMMENT 'Durée de lecture en secondes, calculée à la fermeture',
    metadata JSON COMMENT 'Métadonnées supplémentaires (session RAG, page, etc.)',
    INDEX idx_drs_user (user_id),
    INDEX idx_drs_anonymous (anonymous_id),
    INDEX idx_drs_resource (resource_id),
    INDEX idx_drs_opened_at (opened_at),
    INDEX idx_drs_user_opened (user_id, opened_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- TABLES DU MODÈLE UTILISATEUR, CONNAISSANCES ET OBSERVATIONS
-- (source : app/database/sql_tables_scripts/user_knowledge_model.sql)
-- Vues exclues : seules les tables (CREATE TABLE) sont incluses.
-- =============================================================================

-- Entités (personnes, lieux, œuvres, événements, pratiques)
CREATE TABLE IF NOT EXISTS entities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type ENUM('person', 'place', 'work', 'event', 'practice', 'other') NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Thèmes (hiérarchie via parent_id)
CREATE TABLE IF NOT EXISTS themes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    parent_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES themes(id) ON DELETE SET NULL,
    INDEX idx_themes_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Éléments de connaissance (propositions vérifiables)
CREATE TABLE IF NOT EXISTS knowledge_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    proposition TEXT NOT NULL,
    summary VARCHAR(1000),
    is_verified BOOLEAN DEFAULT FALSE,
    verification_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Association connaissances <-> entités
CREATE TABLE IF NOT EXISTS knowledge_item_entities (
    knowledge_id INT NOT NULL,
    entity_id INT NOT NULL,
    relevance DECIMAL(5,4) DEFAULT 1.0,
    PRIMARY KEY (knowledge_id, entity_id),
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    INDEX idx_kie_knowledge (knowledge_id),
    INDEX idx_kie_entity (entity_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Association connaissances <-> thèmes
CREATE TABLE IF NOT EXISTS knowledge_item_themes (
    knowledge_id INT NOT NULL,
    theme_id INT NOT NULL,
    relevance DECIMAL(5,4) DEFAULT 1.0,
    PRIMARY KEY (knowledge_id, theme_id),
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    FOREIGN KEY (theme_id) REFERENCES themes(id) ON DELETE CASCADE,
    INDEX idx_kit_knowledge (knowledge_id),
    INDEX idx_kit_theme (theme_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Sources des connaissances (chunks, extraits, pages, URI)
CREATE TABLE IF NOT EXISTS knowledge_sources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    knowledge_id INT NOT NULL,
    chunk_id VARCHAR(255) NOT NULL,
    excerpt TEXT,
    page VARCHAR(100),
    uri VARCHAR(1000),
    confidence DECIMAL(3,2) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    INDEX idx_ks_knowledge (knowledge_id),
    INDEX idx_ks_chunk (chunk_id),
    UNIQUE KEY uk_knowledge_chunk_excerpt (knowledge_id, chunk_id, excerpt(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Association connaissances <-> questions
CREATE TABLE IF NOT EXISTS knowledge_item_questions (
    knowledge_id INT NOT NULL,
    question_id INT NOT NULL,
    relevance DECIMAL(5,4) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (knowledge_id, question_id),
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    INDEX idx_kiq_knowledge (knowledge_id),
    INDEX idx_kiq_question (question_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Observations (événements horodatés, non des conclusions)
CREATE TABLE IF NOT EXISTS observations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    observation_type ENUM('declarative', 'behavioral', 'evaluative') NOT NULL,
    specific_type VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    context JSON NOT NULL,
    confidence DECIMAL(3,2) DEFAULT 1.0,
    is_raw BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_observations_user (user_id),
    INDEX idx_observations_type (observation_type),
    INDEX idx_observations_specific_type (specific_type),
    INDEX idx_observations_timestamp (timestamp),
    INDEX idx_observations_user_timestamp (user_id, timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Charges utiles des observations (brut, structuré, traité, interprétation LLM)
CREATE TABLE IF NOT EXISTS observation_payloads (
    observation_id BIGINT NOT NULL,
    payload_type ENUM('raw', 'structured', 'processed', 'llm_interpretation') NOT NULL,
    payload JSON NOT NULL,
    metadata JSON,
    PRIMARY KEY (observation_id, payload_type),
    FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Cibles des observations (connaissance, thème, entité, chunk)
CREATE TABLE IF NOT EXISTS observation_targets (
    observation_id BIGINT NOT NULL,
    target_type ENUM('knowledge', 'theme', 'entity', 'chunk') NOT NULL,
    target_id VARCHAR(255) NOT NULL,
    weight DECIMAL(5,4) DEFAULT 1.0,
    PRIMARY KEY (observation_id, target_type, target_id),
    FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE,
    INDEX idx_ot_observation (observation_id),
    INDEX idx_ot_target (target_type, target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Interprétations produites par les LLM
CREATE TABLE IF NOT EXISTS llm_interpretations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    observation_id BIGINT NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50),
    model_provider VARCHAR(50),
    prompt TEXT NOT NULL,
    temperature DECIMAL(5,2),
    interpretation JSON NOT NULL,
    confidence DECIMAL(3,2) NOT NULL,
    inference_time_ms INT,
    token_count_prompt INT,
    token_count_completion INT,
    total_cost DECIMAL(10,6),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE,
    INDEX idx_li_observation (observation_id),
    INDEX idx_li_model (model_name),
    INDEX idx_li_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Profils utilisateurs
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id VARCHAR(100) PRIMARY KEY,
    languages JSON DEFAULT (JSON_ARRAY()),
    visit_goal TEXT,
    detail_level ENUM('beginner', 'intermediate', 'advanced', 'expert'),
    accessibility_needs JSON DEFAULT (JSON_ARRAY()),
    preferences JSON,
    is_active BOOLEAN DEFAULT TRUE,
    last_activity_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Intérêts utilisateurs par thème
CREATE TABLE IF NOT EXISTS user_interests_themes (
    user_id VARCHAR(100) NOT NULL,
    theme_id INT NOT NULL,
    weight DECIMAL(5,4) DEFAULT 0.5,
    confidence DECIMAL(3,2) DEFAULT 0.5,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, theme_id),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    FOREIGN KEY (theme_id) REFERENCES themes(id) ON DELETE CASCADE,
    INDEX idx_uit_user (user_id),
    INDEX idx_uit_theme (theme_id),
    INDEX idx_uit_weight (user_id, weight)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Intérêts utilisateurs par entité
CREATE TABLE IF NOT EXISTS user_interests_entities (
    user_id VARCHAR(100) NOT NULL,
    entity_id INT NOT NULL,
    weight DECIMAL(5,4) DEFAULT 0.5,
    confidence DECIMAL(3,2) DEFAULT 0.5,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, entity_id),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    INDEX idx_uye_user (user_id),
    INDEX idx_uye_entity (entity_id),
    INDEX idx_uye_weight (user_id, weight)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- États de connaissance des utilisateurs
CREATE TABLE IF NOT EXISTS user_knowledge_states (
    user_id VARCHAR(100) NOT NULL,
    knowledge_id INT NOT NULL,
    status ENUM('unknown', 'encountered', 'developing', 'demonstrated') NOT NULL DEFAULT 'unknown',
    score DECIMAL(3,2) DEFAULT 0.0,
    confidence DECIMAL(3,2) DEFAULT 0.5,
    last_interaction_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, knowledge_id),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    INDEX idx_uks_user (user_id),
    INDEX idx_uks_knowledge (knowledge_id),
    INDEX idx_uks_status (user_id, status),
    INDEX idx_uks_score (user_id, score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Preuves du modèle (lien observations -> état du modèle utilisateur)
CREATE TABLE IF NOT EXISTS model_evidences (
    user_id VARCHAR(100) NOT NULL,
    evidence_type ENUM('profile', 'interest_theme', 'interest_entity', 'knowledge_state') NOT NULL,
    reference_id INT NOT NULL,
    observation_id BIGINT NOT NULL,
    weight DECIMAL(5,4) DEFAULT 1.0,
    contribution_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, evidence_type, reference_id, observation_id),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE,
    INDEX idx_me_user (user_id),
    INDEX idx_me_evidence_type (evidence_type),
    INDEX idx_me_observation (observation_id),
    INDEX idx_me_reference (evidence_type, reference_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Sessions utilisateurs (distincte de la table sessions du RAG)
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    device_type VARCHAR(50),
    user_agent VARCHAR(500),
    ip_address VARCHAR(45),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE,
    duration_seconds INT,
    metadata JSON,
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    INDEX idx_sessions_user (user_id),
    INDEX idx_sessions_started (started_at),
    INDEX idx_sessions_active (user_id, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Historique des changements du modèle utilisateur
CREATE TABLE IF NOT EXISTS user_model_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    change_type ENUM('profile_update', 'interest_added', 'interest_updated', 'interest_removed',
                     'knowledge_state_changed', 'model_recalculated') NOT NULL,
    affected_table VARCHAR(50) NOT NULL,
    affected_id INT,
    old_value JSON,
    new_value JSON,
    trigger_observation_id BIGINT,
    changed_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    FOREIGN KEY (trigger_observation_id) REFERENCES observations(id) ON DELETE SET NULL,
    INDEX idx_umh_user (user_id),
    INDEX idx_umh_change_type (change_type),
    INDEX idx_umh_created (created_at),
    INDEX idx_umh_trigger_obs (trigger_observation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
