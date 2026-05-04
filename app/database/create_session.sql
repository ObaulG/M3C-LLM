CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE sessions (
    session_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    document_id VARCHAR(255) NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    CONSTRAINT valid_session CHECK (ended_at IS NULL OR ended_at > started_at)
);

CREATE TABLE session_answers (
    answer_id SERIAL PRIMARY KEY,
    session_id INT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    question_id INT NOT NULL REFERENCES questions(question_id) ON DELETE CASCADE,
    answer_text TEXT NOT NULL,
    llm_comment TEXT,
    llm_rating INT,
    llm_model VARCHAR(100),  -- Ex: "mistral-tiny", "mistral-small", etc.
    answered_at TIMESTAMP DEFAULT NOW()
);