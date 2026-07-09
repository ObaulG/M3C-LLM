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
