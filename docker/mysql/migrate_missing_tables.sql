-- =============================================================================
-- SCRIPT DE MIGRATION POUR BASE M3C EXISTANTE
-- =============================================================================
-- Ce script cree les tables et vues manquantes sur une base MySQL deja
-- existante (ex: serveurs M3C). Toutes les tables utilisent IF NOT EXISTS,
-- les vues utilisent CREATE OR REPLACE : le script est idempotent et ne
-- modifie pas les tables/vues deja presentes avec le meme schema.
--
-- Utilisation :
--   mysql -h <host> -u <user> -p <database> < migrate_missing_tables.sql
-- ou executer via un client MySQL (DBeaver, HeidiSQL, mysql CLI...).
--
-- ATTENTION : verifier que l'utilisateur a les droits CREATE/ALTER sur la
-- base cible. Le script ne cree ni la base ni l'utilisateur (deja existants).
-- =============================================================================

SET SQL_MODE = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION';

-- =============================================================================
-- TABLES (source : docker/mysql/init.sql, sans creation base/user)
-- =============================================================================

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

-- =============================================================================
-- TABLES DE FEEDBACK CHATBOT
-- (source : app/database/sql_tables_scripts/chatbot_feedback.sql)
-- =============================================================================

-- Une ligne par reponse generee par un LLM, avec la requete utilisateur en amont
-- et les metadonnees de generation (modele, k, temps, tokens, energie...).
CREATE TABLE IF NOT EXISTS chatbot_messages (
    message_id          VARCHAR(64) PRIMARY KEY,
    user_id             VARCHAR(100) NULL,
    session_id          VARCHAR(100) NULL,
    question            TEXT NOT NULL,
    answer              TEXT NOT NULL,
    model               VARCHAR(100) NOT NULL,
    use_rag             BOOLEAN DEFAULT FALSE,
    use_reranking       BOOLEAN DEFAULT FALSE,
    k                   INT NULL,
    total_time          FLOAT NULL,
    consumed_energy_Wh  FLOAT NULL,
    token_usage         JSON NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_cbm_user (user_id, created_at),
    INDEX idx_cbm_session (session_id),
    INDEX idx_cbm_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- IDs de chunks utilises quand le RAG est actif
CREATE TABLE IF NOT EXISTS chatbot_message_chunks (
    message_id          VARCHAR(64) NOT NULL,
    chunk_id            VARCHAR(255) NOT NULL,
    position            INT NOT NULL,
    score_cossim        FLOAT NULL,
    score_bm25          FLOAT NULL,
    PRIMARY KEY (message_id, chunk_id),
    FOREIGN KEY (message_id) REFERENCES chatbot_messages(message_id) ON DELETE CASCADE,
    INDEX idx_cbmc_message (message_id),
    INDEX idx_cbmc_chunk (chunk_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Retour utilisateur (echelles 1-5 + commentaire libre) rattache a un message.
-- Un seul feedback par message (UNIQUE(message_id)).
CREATE TABLE IF NOT EXISTS chatbot_feedbacks (
    feedback_id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    message_id          VARCHAR(64) NOT NULL,
    user_id             VARCHAR(100) NULL,
    rating_response     TINYINT NULL,
    rating_relevance    TINYINT NULL,
    rating_formulation  TINYINT NULL,
    comment             TEXT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_cbf_message (message_id),
    FOREIGN KEY (message_id) REFERENCES chatbot_messages(message_id) ON DELETE CASCADE,
    INDEX idx_cbf_user (user_id, created_at),
    INDEX idx_cbf_created (created_at),
    CONSTRAINT chk_cbf_rating_response    CHECK (rating_response    IS NULL OR rating_response    BETWEEN 1 AND 5),
    CONSTRAINT chk_cbf_rating_relevance   CHECK (rating_relevance   IS NULL OR rating_relevance   BETWEEN 1 AND 5),
    CONSTRAINT chk_cbf_rating_formulation CHECK (rating_formulation IS NULL OR rating_formulation BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================================================================
-- VUES (source : app/database/sql_tables_scripts/user_knowledge_model.sql
--        et user_profile_views.sql)
-- Syntaxe MySQL 8.0+ (JSON_ARRAYAGG, JSON_OBJECT, CREATE OR REPLACE VIEW)
-- =============================================================================

-- --- Vues du modele utilisateur (user_knowledge_model.sql) ---


CREATE OR REPLACE VIEW user_complete_model AS
SELECT
    up.user_id,
    up.languages,
    up.visit_goal,
    up.detail_level,
    up.accessibility_needs,
    up.preferences,
    up.is_active,
    up.last_activity_at,
    up.created_at as profile_created_at,
    up.updated_at as profile_updated_at,
    (
        SELECT JSON_ARRAYAGG(
            JSON_OBJECT(
                'theme_id', uit.theme_id,
                'theme_name', t.name,
                'weight', uit.weight,
                'confidence', uit.confidence,
                'last_updated', uit.last_updated
            )
        )
        FROM user_interests_themes uit
        JOIN themes t ON uit.theme_id = t.id
        WHERE uit.user_id = up.user_id
    ) AS theme_interests,
    (
        SELECT JSON_ARRAYAGG(
            JSON_OBJECT(
                'entity_id', uie.entity_id,
                'entity_name', e.name,
                'entity_type', e.type,
                'weight', uie.weight,
                'confidence', uie.confidence,
                'last_updated', uie.last_updated
            )
        )
        FROM user_interests_entities uie
        JOIN entities e ON uie.entity_id = e.id
        WHERE uie.user_id = up.user_id
    ) AS entity_interests,
    (
        SELECT JSON_ARRAYAGG(
            JSON_OBJECT(
                'knowledge_id', uks.knowledge_id,
                'proposition', ki.proposition,
                'summary', ki.summary,
                'status', uks.status,
                'score', uks.score,
                'confidence', uks.confidence,
                'last_interaction_at', uks.last_interaction_at,
                'created_at', uks.created_at,
                'updated_at', uks.updated_at
            )
        )
        FROM user_knowledge_states uks
        JOIN knowledge_items ki ON uks.knowledge_id = ki.id
        WHERE uks.user_id = up.user_id
    ) AS knowledge_states
FROM user_profiles up;

CREATE OR REPLACE VIEW user_recent_observations AS
SELECT
    o.user_id,
    o.id as observation_id,
    o.observation_type,
    o.specific_type,
    o.timestamp,
    o.confidence,
    o.context,
    (
        SELECT JSON_ARRAYAGG(
            JSON_OBJECT(
                'payload_type', op.payload_type,
                'payload', op.payload
            )
        )
        FROM observation_payloads op
        WHERE op.observation_id = o.id
    ) AS payloads,
    (
        SELECT JSON_ARRAYAGG(
            JSON_OBJECT(
                'target_type', ot.target_type,
                'target_id', ot.target_id,
                'weight', ot.weight
            )
        )
        FROM observation_targets ot
        WHERE ot.observation_id = o.id
    ) AS targets
FROM observations o
ORDER BY o.user_id, o.timestamp DESC;

CREATE OR REPLACE VIEW knowledge_by_themes AS
SELECT
    t.id as theme_id,
    t.name as theme_name,
    t.description as theme_description,
    ki.id as knowledge_id,
    ki.proposition,
    ki.summary,
    kit.relevance as theme_relevance,
    (
        SELECT JSON_ARRAYAGG(
            JSON_OBJECT(
                'entity_id', e.id,
                'entity_name', e.name,
                'entity_type', e.type,
                'relevance', kie.relevance
            )
        )
        FROM knowledge_item_entities kie
        JOIN entities e ON kie.entity_id = e.id
        WHERE kie.knowledge_id = ki.id
    ) AS related_entities,
    (
        SELECT JSON_ARRAYAGG(
            JSON_OBJECT(
                'chunk_id', ks.chunk_id,
                'excerpt', ks.excerpt,
                'page', ks.page,
                'confidence', ks.confidence
            )
        )
        FROM knowledge_sources ks
        WHERE ks.knowledge_id = ki.id
    ) AS sources
FROM knowledge_item_themes kit
JOIN themes t ON kit.theme_id = t.id
JOIN knowledge_items ki ON kit.knowledge_id = ki.id
ORDER BY t.name, kit.relevance DESC, ki.id;

-- --- Vues du profil utilisateur (user_profile_views.sql) ---

CREATE OR REPLACE VIEW user_profile_stats AS
SELECT 
    up.user_id,
    COUNT(DISTINCT o.id) AS total_observations,
    COUNT(DISTINCT CASE WHEN o.observation_type = 'behavioral' AND o.specific_type = 'resource_view' THEN o.id END) AS total_resource_views,
    COUNT(DISTINCT CASE WHEN o.observation_type = 'behavioral' AND o.specific_type = 'theme_view' THEN o.id END) AS total_theme_views,
    COUNT(DISTINCT CASE WHEN o.observation_type = 'evaluative' THEN o.id END) AS total_evaluations,
    COUNT(DISTINCT tc.id) AS total_resources_visited,
    COUNT(DISTINCT t.id) AS total_themes_explored,
    COUNT(DISTINCT ki.id) AS total_knowledge_items_encountered,
    COUNT(DISTINCT CASE WHEN uks.status = 'demonstrated' THEN uks.knowledge_id END) AS total_knowledge_demonstrated,
    COUNT(DISTINCT CASE WHEN uks.status = 'developing' THEN uks.knowledge_id END) AS total_knowledge_developing,
    COUNT(DISTINCT CASE WHEN uks.status = 'encountered' THEN uks.knowledge_id END) AS total_knowledge_encountered,
    COUNT(DISTINCT CASE WHEN uks.status = 'unknown' THEN uks.knowledge_id END) AS total_knowledge_unknown,
    MIN(o.timestamp) AS first_visit,
    MAX(o.timestamp) AS last_visit,
    up.created_at AS profile_created_at,
    up.last_activity_at AS profile_last_activity
FROM user_profiles up
LEFT JOIN observations o ON up.user_id = o.user_id
LEFT JOIN observation_targets ot ON o.id = ot.observation_id AND ot.target_type = 'knowledge'
LEFT JOIN knowledge_items ki ON ot.target_id = ki.id
LEFT JOIN observation_targets ot_chunk ON o.id = ot_chunk.observation_id AND ot_chunk.target_type = 'chunk'
LEFT JOIN text_chunks tc ON tc.id = ot_chunk.target_id
LEFT JOIN knowledge_item_themes kit ON ki.id = kit.knowledge_id
LEFT JOIN themes t ON kit.theme_id = t.id
LEFT JOIN user_knowledge_states uks ON up.user_id = uks.user_id AND uks.knowledge_id = ki.id
WHERE up.user_id IS NOT NULL
GROUP BY up.user_id, up.created_at, up.last_activity_at;

-- ============================================================================
-- VUE 2: Ressources consultées par utilisateur
-- ============================================================================

CREATE OR REPLACE VIEW user_visited_resources AS
SELECT 
    o.user_id,
    tc.id AS chunk_id,
    tc.document_id AS resource_id,
    td.source_type AS resource_type,
    tc.num_page,
    COUNT(DISTINCT o.id) AS view_count,
    MAX(o.timestamp) AS last_viewed_at,
    MIN(o.timestamp) AS first_viewed_at,
    AVG(o.confidence) AS avg_confidence
FROM observations o
JOIN observation_targets ot ON o.id = ot.observation_id AND ot.target_type = 'chunk'
JOIN text_chunks tc ON ot.target_id = tc.id
LEFT JOIN text_documents td ON tc.document_id = td.id
WHERE o.observation_type = 'behavioral' 
    AND o.specific_type = 'resource_view'
GROUP BY o.user_id, tc.id, tc.document_id, td.source_type, tc.num_page
ORDER BY o.user_id, last_viewed_at DESC;

-- ============================================================================
-- VUE 3: Statistiques par thème pour un utilisateur
-- ============================================================================

CREATE OR REPLACE VIEW user_theme_stats AS
SELECT 
    up.user_id,
    t.id AS theme_id,
    t.name AS theme_name,
    t.description AS theme_description,
    COALESCE(uit.weight, 0) AS interest_weight,
    COALESCE(uit.confidence, 0) AS interest_confidence,
    COUNT(DISTINCT o.id) AS observation_count,
    COUNT(DISTINCT CASE WHEN o.observation_type = 'behavioral' THEN o.id END) AS behavioral_count,
    COUNT(DISTINCT CASE WHEN o.observation_type = 'evaluative' THEN o.id END) AS evaluative_count,
    COUNT(DISTINCT ki.id) AS knowledge_items_count,
    COUNT(DISTINCT CASE WHEN uks.status = 'demonstrated' THEN uks.knowledge_id END) AS demonstrated_count,
    COUNT(DISTINCT CASE WHEN uks.status = 'developing' THEN uks.knowledge_id END) AS developing_count,
    MAX(o.timestamp) AS last_interaction_at,
    MIN(o.timestamp) AS first_interaction_at
FROM user_profiles up
LEFT JOIN user_interests_themes uit ON up.user_id = uit.user_id AND t.id = uit.theme_id
LEFT JOIN themes t ON 1=1  -- sera joint plus bas
LEFT JOIN observations o ON up.user_id = o.user_id
LEFT JOIN observation_targets ot ON o.id = ot.observation_id AND ot.target_type = 'theme' AND ot.target_id = t.id
LEFT JOIN knowledge_item_themes kit ON t.id = kit.theme_id
LEFT JOIN knowledge_items ki ON kit.knowledge_id = ki.id
LEFT JOIN user_knowledge_states uks ON up.user_id = uks.user_id AND uks.knowledge_id = ki.id
WHERE up.user_id IS NOT NULL
GROUP BY up.user_id, t.id, t.name, t.description, uit.weight, uit.confidence
HAVING t.id IS NOT NULL
ORDER BY up.user_id, interest_weight DESC, observation_count DESC;

-- Version corrigée avec jointure explicite sur themes
CREATE OR REPLACE VIEW user_theme_stats_v2 AS
SELECT 
    o.user_id,
    t.id AS theme_id,
    t.name AS theme_name,
    t.description AS theme_description,
    COALESCE(uit.weight, 0) AS interest_weight,
    COALESCE(uit.confidence, 0) AS interest_confidence,
    COUNT(DISTINCT o.id) AS observation_count,
    COUNT(DISTINCT CASE WHEN o.observation_type = 'behavioral' THEN o.id END) AS behavioral_count,
    COUNT(DISTINCT CASE WHEN o.observation_type = 'evaluative' THEN o.id END) AS evaluative_count,
    COUNT(DISTINCT ki.id) AS knowledge_items_count,
    COUNT(DISTINCT CASE WHEN uks.status = 'demonstrated' THEN uks.knowledge_id END) AS demonstrated_count,
    COUNT(DISTINCT CASE WHEN uks.status = 'developing' THEN uks.knowledge_id END) AS developing_count,
    COUNT(DISTINCT CASE WHEN uks.status = 'encountered' THEN uks.knowledge_id END) AS encountered_count,
    COUNT(DISTINCT CASE WHEN uks.status = 'unknown' THEN uks.knowledge_id END) AS unknown_count,
    MAX(o.timestamp) AS last_interaction_at,
    MIN(o.timestamp) AS first_interaction_at
FROM observations o
JOIN observation_targets ot_theme ON o.id = ot_theme.observation_id AND ot_theme.target_type = 'theme'
JOIN themes t ON ot_theme.target_id = t.id
LEFT JOIN user_interests_themes uit ON o.user_id = uit.user_id AND t.id = uit.theme_id
LEFT JOIN knowledge_item_themes kit ON t.id = kit.theme_id
LEFT JOIN knowledge_items ki ON kit.knowledge_id = ki.id
LEFT JOIN user_knowledge_states uks ON o.user_id = uks.user_id AND uks.knowledge_id = ki.id
GROUP BY o.user_id, t.id, t.name, t.description, uit.weight, uit.confidence
ORDER BY o.user_id, interest_weight DESC, observation_count DESC;

-- ============================================================================
-- VUE 4: Éléments de connaissance groupés par thème pour un utilisateur
-- ============================================================================

CREATE OR REPLACE VIEW user_knowledge_by_theme AS
SELECT 
    o.user_id,
    t.id AS theme_id,
    t.name AS theme_name,
    ki.id AS knowledge_id,
    ki.proposition,
    ki.summary,
    uks.status AS knowledge_status,
    uks.score AS mastery_score,
    uks.confidence AS confidence,
    uks.last_interaction_at,
    uks.created_at AS knowledge_created_at,
    kit.relevance AS theme_relevance,
    (
        SELECT JSON_ARRAYAGG(
            JSON_OBJECT(
                'entity_id', e.id,
                'entity_name', e.name,
                'entity_type', e.type,
                'relevance', kie.relevance
            )
        )
        FROM knowledge_item_entities kie
        JOIN entities e ON kie.entity_id = e.id
        WHERE kie.knowledge_id = ki.id
    ) AS related_entities,
    (
        SELECT JSON_ARRAYAGG(
            JSON_OBJECT(
                'chunk_id', ks.chunk_id,
                'excerpt', ks.excerpt,
                'page', ks.page,
                'confidence', ks.confidence
            )
        )
        FROM knowledge_sources ks
        WHERE ks.knowledge_id = ki.id
    ) AS sources
FROM observations o
JOIN observation_targets ot_knowledge ON o.id = ot_knowledge.observation_id AND ot_knowledge.target_type = 'knowledge'
JOIN knowledge_items ki ON ot_knowledge.target_id = ki.id
JOIN knowledge_item_themes kit ON ki.id = kit.knowledge_id
JOIN themes t ON kit.theme_id = t.id
JOIN user_knowledge_states uks ON o.user_id = uks.user_id AND uks.knowledge_id = ki.id
GROUP BY o.user_id, t.id, t.name, ki.id, ki.proposition, ki.summary, 
         uks.status, uks.score, uks.confidence, uks.last_interaction_at, uks.created_at, kit.relevance
ORDER BY o.user_id, t.name, kit.relevance DESC, uks.score DESC;

-- ============================================================================
-- VUE 5: Connaissances de l'utilisateur avec leurs thèmes (simplifiée)
-- Utilisée pour l'affichage par thème dans la page de profil
-- ============================================================================

CREATE OR REPLACE VIEW user_knowledge_with_themes AS
SELECT 
    uks.user_id,
    ki.id AS knowledge_id,
    ki.proposition,
    ki.summary,
    uks.status,
    uks.score,
    uks.confidence,
    uks.last_interaction_at,
    uks.created_at,
    (
        SELECT JSON_ARRAYAGG(
            JSON_OBJECT(
                'theme_id', t.id,
                'theme_name', t.name,
                'relevance', kit.relevance
            )
        )
        FROM knowledge_item_themes kit
        JOIN themes t ON kit.theme_id = t.id
        WHERE kit.knowledge_id = ki.id
    ) AS themes,
    (
        SELECT JSON_ARRAYAGG(
            JSON_OBJECT(
                'entity_id', e.id,
                'entity_name', e.name,
                'entity_type', e.type
            )
        )
        FROM knowledge_item_entities kie
        JOIN entities e ON kie.entity_id = e.id
        WHERE kie.knowledge_id = ki.id
    ) AS entities,
    (
        SELECT JSON_ARRAYAGG(
            JSON_OBJECT(
                'chunk_id', ks.chunk_id,
                'excerpt', ks.excerpt
            )
        )
        FROM knowledge_sources ks
        WHERE ks.knowledge_id = ki.id
    ) AS sources
FROM user_knowledge_states uks
JOIN knowledge_items ki ON uks.knowledge_id = ki.id
WHERE uks.user_id IS NOT NULL
ORDER BY uks.user_id, uks.score DESC, uks.confidence DESC;

-- =============================================================================
-- MIGRATION : clé API Mistral personnelle + rôle "guest"
-- =============================================================================
-- La table `user` (externe à ce script) gagne une colonne pour stocker la
-- clé API Mistral de l'utilisateur. Les rôles "admin"/"global_admin" utilisent
-- la clé interne du serveur ; les rôles "user"/"guest" doivent fournir la leur.
-- Idempotent : la colonne n'est ajoutée que si elle n'existe pas.

SET @col_exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'user'
                      AND COLUMN_NAME = 'mistral_api_key');
SET @sql := IF(@col_exists = 0,
    'ALTER TABLE user ADD COLUMN mistral_api_key VARCHAR(255) NULL AFTER password_hash',
    'SELECT "colonne mistral_api_key deja presente" AS info');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Tout compte créé via l'inscription publique prend désormais le rôle "guest".
UPDATE user SET role = 'guest' WHERE role = 'user';
