-- ============================================================================
-- VUES SQL POUR LA PAGE DE PROFIL UTILISATEUR
-- ============================================================================
-- Ces vues permettent d'agréger les données nécessaires à l'affichage du profil
-- Basé sur le schéma user_knowledge_model.sql

-- ============================================================================
-- VUE 1: Statistiques globales par utilisateur
-- ============================================================================

CREATE OR REPLACE VIEW user_profile_stats AS
SELECT 
    up.user_id,
    COUNT(DISTINCT o.id) AS total_observations,
    COUNT(DISTINCT CASE WHEN o.observation_type = 'behavioral' AND o.specific_type = 'resource_view' THEN o.id END) AS total_resource_views,
    COUNT(DISTINCT CASE WHEN o.observation_type = 'behavioral' AND o.specific_type = 'theme_view' THEN o.id END) AS total_theme_views,
    COUNT(DISTINCT CASE WHEN o.observation_type = 'evaluative' THEN o.id END) AS total_evaluations,
    COUNT(DISTINCT kr.id) AS total_resources_visited,
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
LEFT JOIN observation_targets ot_resource ON o.id = ot_resource.observation_id AND ot_resource.target_type = 'entity'
LEFT JOIN knowledge_resources kr ON kr.id = ot_resource.target_id
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
    kr.id AS resource_id,
    kr.title AS resource_title,
    kr.uri AS resource_uri,
    kr.resource_type,
    kr.author,
    kr.publication_date,
    COUNT(DISTINCT o.id) AS view_count,
    MAX(o.timestamp) AS last_viewed_at,
    MIN(o.timestamp) AS first_viewed_at,
    AVG(o.confidence) AS avg_confidence
FROM observations o
JOIN observation_targets ot ON o.id = ot.observation_id AND ot.target_type = 'entity'
JOIN knowledge_resources kr ON ot.target_id = kr.id
WHERE o.observation_type = 'behavioral' 
    AND o.specific_type = 'resource_view'
GROUP BY o.user_id, kr.id, kr.title, kr.uri, kr.resource_type, kr.author, kr.publication_date
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
                'source_id', ks.resource_id,
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
                'resource_id', ks.resource_id,
                'resource_title', kr.title,
                'excerpt', ks.excerpt
            )
        )
        FROM knowledge_sources ks
        JOIN knowledge_resources kr ON ks.resource_id = kr.id
        WHERE ks.knowledge_id = ki.id
    ) AS sources
FROM user_knowledge_states uks
JOIN knowledge_items ki ON uks.knowledge_id = ki.id
WHERE uks.user_id IS NOT NULL
ORDER BY uks.user_id, uks.score DESC, uks.confidence DESC;
