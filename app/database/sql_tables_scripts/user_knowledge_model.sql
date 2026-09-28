CREATE TABLE IF NOT EXISTS entities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type ENUM('person', 'place', 'work', 'event', 'practice', 'other') NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS themes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    parent_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES themes(id) ON DELETE SET NULL,
    INDEX idx_themes_parent (parent_id)
);

CREATE TABLE IF NOT EXISTS knowledge_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    proposition TEXT NOT NULL,
    summary VARCHAR(1000),
    is_verified BOOLEAN DEFAULT FALSE,
    verification_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_item_entities (
    knowledge_id INT NOT NULL,
    entity_id INT NOT NULL,
    relevance DECIMAL(5,4) DEFAULT 1.0,
    PRIMARY KEY (knowledge_id, entity_id),
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    INDEX idx_kie_knowledge (knowledge_id),
    INDEX idx_kie_entity (entity_id)
);

CREATE TABLE IF NOT EXISTS knowledge_item_themes (
    knowledge_id INT NOT NULL,
    theme_id INT NOT NULL,
    relevance DECIMAL(5,4) DEFAULT 1.0,
    PRIMARY KEY (knowledge_id, theme_id),
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    FOREIGN KEY (theme_id) REFERENCES themes(id) ON DELETE CASCADE,
    INDEX idx_kit_knowledge (knowledge_id),
    INDEX idx_kit_theme (theme_id)
);

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
);

CREATE TABLE IF NOT EXISTS knowledge_item_questions (
    knowledge_id INT NOT NULL,
    question_id INT NOT NULL,
    relevance DECIMAL(5,4) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (knowledge_id, question_id),
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    INDEX idx_kiq_knowledge (knowledge_id),
    INDEX idx_kiq_question (question_id)
);

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
);

CREATE TABLE IF NOT EXISTS observation_payloads (
    observation_id BIGINT NOT NULL,
    payload_type ENUM('raw', 'structured', 'processed', 'llm_interpretation') NOT NULL,
    payload JSON NOT NULL,
    metadata JSON,
    PRIMARY KEY (observation_id, payload_type),
    FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS observation_targets (
    observation_id BIGINT NOT NULL,
    target_type ENUM('knowledge', 'theme', 'entity', 'chunk') NOT NULL,
    target_id VARCHAR(255) NOT NULL,
    weight DECIMAL(5,4) DEFAULT 1.0,
    PRIMARY KEY (observation_id, target_type, target_id),
    FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE,
    INDEX idx_ot_observation (observation_id),
    INDEX idx_ot_target (target_type, target_id)
);

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
);

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
);

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
);

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
);

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
);

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
);

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
);

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
);

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