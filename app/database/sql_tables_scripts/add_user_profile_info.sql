-- Informations de profil collectées à l'inscription et modifiables depuis
-- la page de profil : sexe, tranche d'âge, statut universitaire et objectifs
-- de recherche sur la M3C (liste de cases à cocher).
-- Table dédiée, la table `user` n'est pas modifiée.
CREATE TABLE IF NOT EXISTS user_profile_info (
    user_id INT NOT NULL COMMENT 'Identifiant de la table user',
    gender VARCHAR(100) COMMENT 'Sexe : Femme / Homme / Autre',
    age_range VARCHAR(50) COMMENT 'Tranche d''âge',
    academic_status VARCHAR(100) COMMENT 'Statut universitaire',
    search_goals TEXT COMMENT 'Objectifs de recherche sur la M3C (liste en JSON)',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Date de création de la ligne',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Date de dernière modification',
    PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
