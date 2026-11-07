-- Script SQL pour créer les tables de gestion des sessions de questions
-- Ces tables permettent de définir des sessions prédéfinies (titre, description, liste de questions)
-- distinctement des sessions utilisateur (stockées dans la table `sessions`)

-- Table pour les définitions de sessions de questions
CREATE TABLE IF NOT EXISTS question_sessions (
    session_id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    document_id INT,
    created_by INT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (document_id) REFERENCES text_documents(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES user(id) ON DELETE SET NULL,
    INDEX idx_question_sessions_document (document_id),
    INDEX idx_question_sessions_created_by (created_by)
);

-- Table de liaison pour associer les questions à une session (avec ordre)
CREATE TABLE IF NOT EXISTS question_session_questions (
    session_id INT NOT NULL,
    question_id BIGINT UNSIGNED NOT NULL,
    order_index INT NOT NULL,
    PRIMARY KEY (session_id, question_id),
    FOREIGN KEY (session_id) REFERENCES question_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES text_questions(question_id) ON DELETE CASCADE,
    INDEX idx_question_session_questions_order (session_id, order_index)
);

-- Vérification que les tables ont été créées
SELECT 
    'question_sessions' AS table_name,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'question_sessions') 
         THEN '✅ Table existe' 
         ELSE '❌ Table manquante' END AS status
UNION ALL
SELECT 
    'question_session_questions' AS table_name,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'question_session_questions') 
         THEN '✅ Table existe' 
         ELSE '❌ Table manquante' END AS status;
