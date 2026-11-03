-- =============================================================================
-- TABLE : cl\u00e9 API Mistral personnelle des utilisateurs
-- =============================================================================
-- Stocke la cl\u00e9 API Mistral de chaque utilisateur dans une table d\u00e9di\u00e9e,
-- s\u00e9par\u00e9e de la table `user` (que l'application ne modifie pas).
-- Une ligne par utilisateur (user_id = cl\u00e9 primaire) ; la cl\u00e9 est effac\u00e9e
-- en supprimant la ligne.

CREATE TABLE IF NOT EXISTS user_mistral_api_keys (
    user_id INT NOT NULL COMMENT 'Identifiant de la table user',
    mistral_api_key VARCHAR(255) NOT NULL COMMENT 'Cl\u00e9 API Mistral personnelle de l\u2019utilisateur',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Date de cr\u00e9ation de la ligne',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Date de derni\u00e8re modification',
    PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
