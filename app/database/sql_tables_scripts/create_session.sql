CREATE TABLE IF NOT EXISTS sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    user_id INT,
    document_id VARCHAR(255) NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE,
    CONSTRAINT valid_session CHECK (ended_at IS NULL OR ended_at > started_at),
    INDEX idx_sessions_user (user_id),
    INDEX idx_sessions_document (document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS session_answers (
    answer_id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    question_id INT NOT NULL,
    question_text TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    llm_comment TEXT,
    llm_rating INT,
    llm_model VARCHAR(100),  -- Ex: "mistral-tiny", "mistral-small", etc.
    message_type VARCHAR(50),  -- Type retourné par l'évaluateur: "réponse", "demande_renseignement", "hors_sujet", "autre"
    answered_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    INDEX idx_session_answers_question (question_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
