CREATE TABLE text_questions (
    question_id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,  -- Texte de la question
    status ENUM('generated', 'pending', 'validated', 'rejected') NOT NULL,  -- "generated", "pending", "validated", "rejected"
    difficulty_level INT,  -- Niveau de difficulté (1-5)
    created_by INT REFERENCES users(user_id),  -- Qui a généré la question (IA = NULL, humain = user_id)
    model VARCHAR(32), -- Référence le modèle utilisé si la question a été générée.
    validated_by INT REFERENCES users(user_id),  -- Qui a validé la question
    validation_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
);

--Une question peut faire intervenir plusieurs chunks.
--Un chunk peut intervenir dans plusieurs questions.
CREATE TABLE text_question_chunks (
    question_id INT NOT NULL REFERENCES questions(question_id) ON DELETE CASCADE,
    chunk_id VARCHAR(255) NOT NULL REFERENCES text_chunks(id) ON DELETE CASCADE,
    PRIMARY KEY (question_id, chunk_id)
);

--Réponses de référence pour les questions
CREATE TABLE text_question_answers (
    answer_id SERIAL PRIMARY KEY,
    question_id INT NOT NULL REFERENCES questions(question_id) ON DELETE CASCADE,
    content TEXT NOT NULL,  -- Réponse attendue ou réponse de l'utilisateur
    is_correct BOOLEAN,  -- Si c'est une réponse attendue, est-elle correcte ?
    created_by INT REFERENCES users(user_id),  -- Qui a fourni la réponse
    created_at TIMESTAMP DEFAULT NOW()
);
