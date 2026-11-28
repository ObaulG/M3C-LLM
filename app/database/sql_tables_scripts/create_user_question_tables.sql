DROP TABLE IF EXISTS text_question_answers;
DROP TABLE IF EXISTS text_question_chunks;
DROP TABLE IF EXISTS text_questions;
DROP TABLE IF EXISTS user_profile_info;
DROP TABLE IF EXISTS `user`;

CREATE TABLE IF NOT EXISTS `user` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    mistral_api_key VARCHAR(255),
    `role` ENUM('global_admin', 'admin', 'validator', 'user', 'guest') NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    modified_at TIMESTAMP DEFAULT NOW(),
    validator BOOLEAN DEFAULT FALSE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Informations de profil facultatives (sexe, tranche d'âge, statut universitaire,
-- objectifs de recherche sur la M3C), dans une table dédiée : la table user
-- n'est pas modifiée.
CREATE TABLE IF NOT EXISTS user_profile_info (
    user_id INT PRIMARY KEY,
    gender VARCHAR(100),
    age_range VARCHAR(50),
    academic_status VARCHAR(100),
    search_goals TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    modified_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES `user`(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS text_questions (
    question_id INT AUTO_INCREMENT PRIMARY KEY,
    content TEXT NOT NULL,  -- Texte de la question
    status ENUM('generated', 'pending', 'validated', 'rejected') NOT NULL,  -- "generated", "pending", "validated", "rejected"
    difficulty_level INT,  -- Niveau de difficulté (1-5)
    created_by INT,  -- Qui a généré la question (IA = NULL, humain = user_id)
    model VARCHAR(32), -- Référence le modèle utilisé si la question a été générée.
    validated_by INT,  -- Qui a validé la question
    validation_date TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (created_by) REFERENCES `user`(id),
    FOREIGN KEY (validated_by) REFERENCES `user`(id),
    INDEX idx_text_questions_status (status),
    INDEX idx_text_questions_difficulty (difficulty_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Une question peut faire intervenir plusieurs chunks.
-- Un chunk peut intervenir dans plusieurs questions.
-- Remarque : la clé étrangère vers text_chunks(id) est omise, la table
-- text_chunks étant créée par chunks.sql.
CREATE TABLE IF NOT EXISTS text_question_chunks (
    question_id INT NOT NULL,
    chunk_id VARCHAR(255) NOT NULL,
    PRIMARY KEY (question_id, chunk_id),
    FOREIGN KEY (question_id) REFERENCES text_questions(question_id) ON DELETE CASCADE,
    INDEX idx_text_question_chunks_chunk (chunk_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Réponses de référence pour les questions
CREATE TABLE IF NOT EXISTS text_question_answers (
    answer_id INT AUTO_INCREMENT PRIMARY KEY,
    question_id INT NOT NULL,
    content TEXT NOT NULL,  -- Réponse attendue ou réponse de l'utilisateur
    is_correct BOOLEAN,  -- Si c'est une réponse attendue, est-elle correcte ?
    created_by INT,  -- Qui a fourni la réponse
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (question_id) REFERENCES text_questions(question_id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES `user`(id),
    INDEX idx_text_question_answers_question (question_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
