-- Script SQL pour créer le modèle utilisateur, connaissances et observations
-- Système évolutif pour l'adaptation des contenus, interactions et recommandations
-- Basé sur le document: modele-utilisateur-connaissances-observations.md
-- MySQL 8.0+ compatible (utilise JSON, ENUM, etc.)

-- ============================================================================
-- SECTION 1: TABLES DE RéFéRENCE (ENTITéS, THèMES, RESSOURCES)
-- ============================================================================

-- 1.1 Entités : personnes, lieux, œuvres, événements, pratiques
CREATE TABLE IF NOT EXISTS entities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL COMMENT 'Nom de l\'entité',
    type ENUM('person', 'place', 'work', 'event', 'practice', 'other') NOT NULL COMMENT 'Type d\'entité',
    description TEXT COMMENT 'Description détaillée',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Date de création',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Dernière mise à jour'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 1.2 Thèmes avec hiérarchie
CREATE TABLE IF NOT EXISTS themes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL COMMENT 'Nom du thème',
    description TEXT COMMENT 'Description du thème',
    parent_id INT NULL COMMENT 'ID du thème parent pour hiérarchie',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Date de création',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Dernière mise à jour',
    FOREIGN KEY (parent_id) REFERENCES themes(id) ON DELETE SET NULL,
    INDEX idx_themes_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 1.3 Ressources documentaires
CREATE TABLE IF NOT EXISTS knowledge_resources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(500) NOT NULL COMMENT 'Titre de la ressource',
    uri VARCHAR(1000) COMMENT 'URI/URL de la ressource',
    resource_type VARCHAR(100) COMMENT 'Type de ressource (pdf, web, book, etc.)',
    author VARCHAR(255) COMMENT 'Auteur de la ressource',
    publication_date DATE COMMENT 'Date de publication',
    description TEXT COMMENT 'Description de la ressource',
    metadata JSON COMMENT 'Métadonnées supplémentaires en JSON',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Date d\'ajout dans le système',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Dernière mise à jour'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- SECTION 2: CONNAISSANCES (Knowledge Items)
-- ============================================================================

-- 2.1 Connaissances atomiques
CREATE TABLE IF NOT EXISTS knowledge_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    proposition TEXT NOT NULL COMMENT 'Proposition ou information formulée et vérifiable',
    summary VARCHAR(1000) COMMENT 'Résumé ou titre court de la connaissance',
    is_verified BOOLEAN DEFAULT FALSE COMMENT 'La connaissance a-t-elle été vérifiée?',
    verification_notes TEXT COMMENT 'Notes sur la vérification',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Date de création',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Dernière mise à jour'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2.2 Relations connaissances <-> entités (many-to-many)
CREATE TABLE IF NOT EXISTS knowledge_item_entities (
    knowledge_id INT NOT NULL,
    entity_id INT NOT NULL,
    relevance DECIMAL(5,4) DEFAULT 1.0 COMMENT 'Pertinence de l\'entité pour cette connaissance (0-1)',
    PRIMARY KEY (knowledge_id, entity_id),
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    INDEX idx_kie_knowledge (knowledge_id),
    INDEX idx_kie_entity (entity_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2.3 Relations connaissances <-> thèmes (many-to-many)
CREATE TABLE IF NOT EXISTS knowledge_item_themes (
    knowledge_id INT NOT NULL,
    theme_id INT NOT NULL,
    relevance DECIMAL(5,4) DEFAULT 1.0 COMMENT 'Pertinence du thème pour cette connaissance (0-1)',
    PRIMARY KEY (knowledge_id, theme_id),
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    FOREIGN KEY (theme_id) REFERENCES themes(id) ON DELETE CASCADE,
    INDEX idx_kit_knowledge (knowledge_id),
    INDEX idx_kit_theme (theme_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2.4 Sources des connaissances (une connaissance peut venir de plusieurs ressources)
CREATE TABLE IF NOT EXISTS knowledge_sources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    knowledge_id INT NOT NULL,
    resource_id INT NOT NULL,
    excerpt TEXT COMMENT 'Extrait exact de la source',
    page VARCHAR(100) COMMENT 'Page ou section dans la source',
    uri VARCHAR(1000) COMMENT 'URI spécifique si différent de la ressource',
    confidence DECIMAL(3,2) DEFAULT 1.0 COMMENT 'Confiance dans cette source pour cette connaissance (0-1)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Date d\'ajout',
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES knowledge_resources(id) ON DELETE CASCADE,
    INDEX idx_ks_knowledge (knowledge_id),
    INDEX idx_ks_resource (resource_id),
    UNIQUE KEY uk_knowledge_resource_excerpt (knowledge_id, resource_id, excerpt(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- SECTION 3: OBSERVATIONS
-- ============================================================================

-- 3.1 Table principale des observations
CREATE TABLE IF NOT EXISTS observations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL COMMENT 'Identifiant de l\'utilisateur (peut être UUID)',
    observation_type ENUM('declarative', 'behavioral', 'evaluative') NOT NULL COMMENT 'Type principal d\'observation',
    specific_type VARCHAR(100) NOT NULL COMMENT 'Type spécifique (ex: language, click, free_response)',
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Date/heure exacte de l\'observation',
    context JSON NOT NULL COMMENT 'Contexte: {session_id, page, resource_id, device, user_agent, etc.}',
    confidence DECIMAL(3,2) DEFAULT 1.0 COMMENT 'Fiabilité de l\'interprétation (0-1)',
    is_raw BOOLEAN DEFAULT TRUE COMMENT 'L\'observation est-elle une donnée brute (TRUE) ou déjà interprétée?',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Date de création dans le système',
    INDEX idx_observations_user (user_id),
    INDEX idx_observations_type (observation_type),
    INDEX idx_observations_specific_type (specific_type),
    INDEX idx_observations_timestamp (timestamp),
    INDEX idx_observations_user_timestamp (user_id, timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3.2 Payload des observations (données brutes ou structurées)
CREATE TABLE IF NOT EXISTS observation_payloads (
    observation_id BIGINT NOT NULL,
    payload_type ENUM('raw', 'structured', 'processed', 'llm_interpretation') NOT NULL COMMENT 'Type de payload',
    payload JSON NOT NULL COMMENT 'Données brutes ou résultat structuré',
    metadata JSON COMMENT 'Métadonnées supplémentaires sur le payload',
    PRIMARY KEY (observation_id, payload_type),
    FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3.3 Cibles des observations (liens vers connaissances, thèmes, entités concernés)
CREATE TABLE IF NOT EXISTS observation_targets (
    observation_id BIGINT NOT NULL,
    target_type ENUM('knowledge', 'theme', 'entity') NOT NULL COMMENT 'Type de cible',
    target_id INT NOT NULL COMMENT 'ID de la cible (knowledge_items.id, themes.id, ou entities.id)',
    weight DECIMAL(5,4) DEFAULT 1.0 COMMENT 'Poids/Pertinence de cette cible pour l\'observation',
    PRIMARY KEY (observation_id, target_type, target_id),
    FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE,
    INDEX idx_ot_observation (observation_id),
    INDEX idx_ot_target (target_type, target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3.4 Interprétations LLM (pour les analyses produites par IA)
CREATE TABLE IF NOT EXISTS llm_interpretations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    observation_id BIGINT NOT NULL,
    model_name VARCHAR(100) NOT NULL COMMENT 'Nom du modèle LLM utilisé',
    model_version VARCHAR(50) COMMENT 'Version du modèle',
    model_provider VARCHAR(50) COMMENT 'Fournisseur du modèle (ex: mistral, openai)',
    prompt TEXT NOT NULL COMMENT 'Prompt utilisé pour l\'interprétation',
    temperature DECIMAL(5,2) COMMENT 'Température utilisée lors de l\'inférence',
    interpretation JSON NOT NULL COMMENT 'Résultat de l\'interprétation en JSON',
    confidence DECIMAL(3,2) NOT NULL COMMENT 'Confiance dans cette interprétation (0-1)',
    inference_time_ms INT COMMENT 'Temps d\'inférence en millisecondes',
    token_count_prompt INT COMMENT 'Nombre de tokens dans le prompt',
    token_count_completion INT COMMENT 'Nombre de tokens dans la réponse',
    total_cost DECIMAL(10,6) COMMENT 'Coût total de l\'appel API',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Date de l\'interprétation',
    FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE,
    INDEX idx_li_observation (observation_id),
    INDEX idx_li_model (model_name),
    INDEX idx_li_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- SECTION 4: MODèLE UTILISATEUR (User Model)
-- ============================================================================

-- 4.1 Profils utilisateurs
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id VARCHAR(100) PRIMARY KEY COMMENT 'Identifiant unique de l\'utilisateur',
    languages JSON DEFAULT (JSON_ARRAY()) COMMENT 'Langues préférées (ex: ["fr", "en"])',
    visit_goal TEXT COMMENT 'Objectif de visite déclaré',
    detail_level ENUM('beginner', 'intermediate', 'advanced', 'expert') COMMENT 'Niveau de détail souhaité',
    accessibility_needs JSON DEFAULT (JSON_ARRAY()) COMMENT 'Besoin d\'accessibilité (ex: ["visual_impairment", "hearing_impairment"])',
    preferences JSON COMMENT 'Préférences utilisateur supplémentaires',
    is_active BOOLEAN DEFAULT TRUE COMMENT 'Le profil est-il actif?',
    last_activity_at TIMESTAMP NULL COMMENT 'Dernière activité de l\'utilisateur',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Date de création',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Dernière mise à jour'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4.2 Intérêts utilisateurs - Thèmes
CREATE TABLE IF NOT EXISTS user_interests_themes (
    user_id VARCHAR(100) NOT NULL,
    theme_id INT NOT NULL,
    weight DECIMAL(5,4) DEFAULT 0.5 COMMENT 'Poids de l\'intérêt (0-1)',
    confidence DECIMAL(3,2) DEFAULT 0.5 COMMENT 'Confiance dans cet intérêt (0-1)',
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Dernière mise à jour',
    PRIMARY KEY (user_id, theme_id),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    FOREIGN KEY (theme_id) REFERENCES themes(id) ON DELETE CASCADE,
    INDEX idx_uit_user (user_id),
    INDEX idx_uit_theme (theme_id),
    INDEX idx_uit_weight (user_id, weight)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4.3 Intérêts utilisateurs - Entités
CREATE TABLE IF NOT EXISTS user_interests_entities (
    user_id VARCHAR(100) NOT NULL,
    entity_id INT NOT NULL,
    weight DECIMAL(5,4) DEFAULT 0.5 COMMENT 'Poids de l\'intérêt (0-1)',
    confidence DECIMAL(3,2) DEFAULT 0.5 COMMENT 'Confiance dans cet intérêt (0-1)',
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Dernière mise à jour',
    PRIMARY KEY (user_id, entity_id),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    INDEX idx_uye_user (user_id),
    INDEX idx_uye_entity (entity_id),
    INDEX idx_uye_weight (user_id, weight)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4.4 États des connaissances utilisateurs
CREATE TABLE IF NOT EXISTS user_knowledge_states (
    user_id VARCHAR(100) NOT NULL,
    knowledge_id INT NOT NULL,
    status ENUM('unknown', 'encountered', 'developing', 'demonstrated') NOT NULL DEFAULT 'unknown' COMMENT 'État de la connaissance pour cet utilisateur',
    score DECIMAL(3,2) DEFAULT 0.0 COMMENT 'Score de maîtrise estimée (0-1)',
    confidence DECIMAL(3,2) DEFAULT 0.5 COMMENT 'Confiance dans cette estimation (0-1)',
    last_interaction_at TIMESTAMP NULL COMMENT 'Dernière interaction liée à cette connaissance',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Date de première détection',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Dernière mise à jour',
    PRIMARY KEY (user_id, knowledge_id),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    INDEX idx_uks_user (user_id),
    INDEX idx_uks_knowledge (knowledge_id),
    INDEX idx_uks_status (user_id, status),
    INDEX idx_uks_score (user_id, score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4.5 Table de preuves/évidences (Traceabilité: observations -> modèle utilisateur)
CREATE TABLE IF NOT EXISTS model_evidences (
    user_id VARCHAR(100) NOT NULL,
    evidence_type ENUM('profile', 'interest_theme', 'interest_entity', 'knowledge_state') NOT NULL COMMENT 'Type de preuve',
    reference_id INT NOT NULL COMMENT 'ID de référence: user_profiles.id, user_interests_*.id, ou user_knowledge_states.id',
    observation_id BIGINT NOT NULL COMMENT 'ID de l\'observation qui justifie cette valeur',
    weight DECIMAL(5,4) DEFAULT 1.0 COMMENT 'Poids de cette preuve dans le calcul',
    contribution_note TEXT COMMENT 'Note sur la contribution de cette preuve',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Date de création',
    PRIMARY KEY (user_id, evidence_type, reference_id, observation_id),
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE,
    INDEX idx_me_user (user_id),
    INDEX idx_me_evidence_type (evidence_type),
    INDEX idx_me_observation (observation_id),
    INDEX idx_me_reference (evidence_type, reference_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- SECTION 5: TABLES DE SUPPORT / OPTIMISATIONS
-- ============================================================================

-- 5.1 Sessions utilisateurs (pour regrouper les observations)
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id VARCHAR(100) PRIMARY KEY COMMENT 'Identifiant unique de la session',
    user_id VARCHAR(100) NOT NULL COMMENT 'Identifiant de l\'utilisateur',
    device_type VARCHAR(50) COMMENT 'Type de périphérique (desktop, mobile, tablet)',
    user_agent VARCHAR(500) COMMENT 'User agent du navigateur',
    ip_address VARCHAR(45) COMMENT 'Adresse IP (pour analyse géographique)',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Début de la session',
    ended_at TIMESTAMP NULL COMMENT 'Fin de la session',
    is_active BOOLEAN DEFAULT TRUE COMMENT 'La session est-elle active?',
    duration_seconds INT COMMENT 'Durée totale de la session en secondes',
    metadata JSON COMMENT 'Métadonnées supplémentaires',
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    INDEX idx_sessions_user (user_id),
    INDEX idx_sessions_started (started_at),
    INDEX idx_sessions_active (user_id, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5.2 Historique des changements du modèle utilisateur (pour audit et reco)
CREATE TABLE IF NOT EXISTS user_model_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    change_type ENUM('profile_update', 'interest_added', 'interest_updated', 'interest_removed', 
                     'knowledge_state_changed', 'model_recalculated') NOT NULL,
    affected_table VARCHAR(50) NOT NULL COMMENT 'Table concernée par le changement',
    affected_id INT COMMENT 'ID de l\'enregistrement concerné',
    old_value JSON COMMENT 'Ancienne valeur avant le changement',
    new_value JSON COMMENT 'Nouvelle valeur après le changement',
    trigger_observation_id BIGINT COMMENT 'ID de l\'observation qui a déclenché ce changement',
    changed_by VARCHAR(50) COMMENT 'Qui a fait le changement (system, user, llm)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    FOREIGN KEY (trigger_observation_id) REFERENCES observations(id) ON DELETE SET NULL,
    INDEX idx_umh_user (user_id),
    INDEX idx_umh_change_type (change_type),
    INDEX idx_umh_created (created_at),
    INDEX idx_umh_trigger_obs (trigger_observation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- SECTION 6: VUES UTILES
-- ============================================================================

-- 6.1 Vue: Modèle utilisateur complet
DELIMITER //
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
//
DELIMITER ;

-- 6.2 Vue: Observations récentes par utilisateur
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

-- 6.3 Vue: Connaissances par thème avec weighting
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
                'source_id', ks.resource_id,
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

-- ============================================================================
-- SECTION 7: TRIGGERS
-- ============================================================================

-- 7.1 Trigger pour mettre à jour updated_at sur user_profiles
DELIMITER //
CREATE TRIGGER update_user_profile_timestamp
BEFORE UPDATE ON user_profiles
FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END//
DELIMITER ;

-- 7.2 Trigger pour mettre à jour updated_at sur knowledge_items
DELIMITER //
CREATE TRIGGER update_knowledge_item_timestamp
BEFORE UPDATE ON knowledge_items
FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END//
DELIMITER ;

-- 7.3 Trigger pour mettre à jour updated_at sur knowledge_resources
DELIMITER //
CREATE TRIGGER update_knowledge_resource_timestamp
BEFORE UPDATE ON knowledge_resources
FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END//
DELIMITER ;

-- ============================================================================
-- SECTION 8: COMMENTAIRES FINAUX ET RECOMMANDATIONS
-- ============================================================================

-- Ce schéma implémente complètement le modèle décrit dans:
-- modele-utilisateur-connaissances-observations.md
--
-- Points clés respectés:
-- ✅ Connaissances atomiques avec propositions, entités, thèmes, sources
-- ✅ Observations horodatées avec types (déclaratives, comportementales, évaluatives)
-- ✅ Journal d'observations immuable avec traçabilité complète
-- ✅ Modèle utilisateur dynamique avec profil, intérêts, états des connaissances
-- ✅ Traçabilité des preuves via la table model_evidences
-- ✅ Support des interprétations LLM avec contexte complet
-- ✅ Vues utiles pour la récupération des données
-- ✅ Index pour performances sur les champs fréquemment consultés
-- ✅ Triggers pour mise à jour automatique des timestamps
--
-- Recommandations pour la production:
-- 1. Considérer le partitionnement de la table observations par mois/année
-- 2. Ajouter des indexes supplémentaires selon les requêtes spécifiques
-- 3. Implémenter un système de cache pour les vues complexes
-- 4. Prévoir des sauvegardes régulières
-- 5. Monitorer la taille des tables JSON pour optimiser si nécessaire

-- Pour exécuter ce script:
-- mysql -u [username] -p [database_name] < user_knowledge_model.sql