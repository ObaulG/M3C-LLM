CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS questions CASCADE;
DROP TABLE IF EXISTS questions_chunks CASCADE;
DROP TABLE IF EXISTS question_answers CASCADE;

CREATE TABLE IF NOT EXISTS user (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    modified_at TIMESTAMP DEFAULT NOW(),
    validator BOOLEAN DEFAULT FALSE,
    CONSTRAINT valid_role CHECK (role IN ('global_admin', 'admin',  'user'))
);

CREATE TABLE IF NOT EXISTS text_questions (
    question_id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,  -- Texte de la question
    status VARCHAR(16) NOT NULL,  -- "generated", "pending", "validated", "rejected"
    difficulty_level INT,  -- Niveau de difficulté (1-5)
    created_by INT REFERENCES users(user_id),  -- Qui a généré la question (IA = NULL, humain = user_id)
    model VARCHAR(32), -- Référence le modèle utilisé si la question a été générée.
    validated_by INT REFERENCES users(user_id),  -- Qui a validé la question
    validation_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT valid_status CHECK (status IN ('generated', 'pending', 'validated', 'rejected'))
);

--Une question peut faire intervenir plusieurs chunks.
--Un chunk peut intervenir dans plusieurs questions.
CREATE TABLE IF NOT EXISTS text_question_chunks (
    question_id INT NOT NULL REFERENCES questions(question_id) ON DELETE CASCADE,
    chunk_id VARCHAR(255) NOT NULL REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    PRIMARY KEY (question_id, chunk_id)
);

--Réponses de référence pour les questions
CREATE TABLE IF NOT EXISTS text_question_answers (
    answer_id SERIAL PRIMARY KEY,
    question_id INT NOT NULL REFERENCES questions(question_id) ON DELETE CASCADE,
    content TEXT NOT NULL,  -- Réponse attendue ou réponse de l'utilisateur
    is_correct BOOLEAN,  -- Si c'est une réponse attendue, est-elle correcte ?
    created_by INT REFERENCES users(id),  -- Qui a fourni la réponse
    created_at TIMESTAMP DEFAULT NOW()
);



CREATE INDEX idx_questions_status ON questions(status);
CREATE INDEX idx_questions_difficulty ON questions(difficulty_level);
CREATE INDEX idx_question_chunks_question ON question_chunks(question_id);
CREATE INDEX idx_question_chunks_chunk ON question_chunks(chunk_id); No newline at end of file