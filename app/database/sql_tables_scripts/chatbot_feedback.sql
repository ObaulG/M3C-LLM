-- =============================================================================
-- Système de retours utilisateurs sur les réponses du chatbot M3C.
--
-- Trois tables :
--   chatbot_messages        : une ligne par réponse générée par un LLM, avec en
--                             amont la requête utilisateur et les métadonnées de
--                             génération (modèle, k, temps, tokens, énergie...).
--   chatbot_message_chunks    : les IDs de chunks utilisés quand le RAG est actif.
--   chatbot_feedbacks        : un retour utilisateur (échelles 1-5 + commentaire
--                             libre) rattaché à un message. Un seul feedback par
--                             message (UNIQUE(message_id)).
-- =============================================================================

CREATE TABLE IF NOT EXISTS chatbot_messages (
    message_id          VARCHAR(64) PRIMARY KEY,          -- UUID généré côté serveur
    user_id             VARCHAR(100) NULL,                -- users.id (connecté) ou anonymous_id
    session_id          VARCHAR(100) NULL,                -- session RAG si applicable
    question            TEXT NOT NULL,                    -- requête utilisateur en amont
    answer              TEXT NOT NULL,                    -- réponse générée par le LLM
    model               VARCHAR(100) NOT NULL,
    use_rag             BOOLEAN DEFAULT FALSE,
    use_reranking       BOOLEAN DEFAULT FALSE,
    k                   INT NULL,
    total_time          FLOAT NULL,                       -- secondes
    consumed_energy_Wh  FLOAT NULL,                       -- modèles locaux uniquement
    token_usage         JSON NULL,                        -- {input_tokens, output_tokens, total_tokens}
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_cbm_user (user_id, created_at),
    INDEX idx_cbm_session (session_id),
    INDEX idx_cbm_created (created_at)
);

CREATE TABLE IF NOT EXISTS chatbot_message_chunks (
    message_id          VARCHAR(64) NOT NULL,
    chunk_id            VARCHAR(255) NOT NULL,            -- text_chunks.id
    position            INT NOT NULL,                     -- ordre dans les sources (0-based)
    score_cossim        FLOAT NULL,
    score_bm25          FLOAT NULL,
    PRIMARY KEY (message_id, chunk_id),
    FOREIGN KEY (message_id) REFERENCES chatbot_messages(message_id) ON DELETE CASCADE,
    INDEX idx_cbmc_message (message_id),
    INDEX idx_cbmc_chunk (chunk_id)
);

CREATE TABLE IF NOT EXISTS chatbot_feedbacks (
    feedback_id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    message_id          VARCHAR(64) NOT NULL,
    user_id             VARCHAR(100) NULL,                 -- users.id ou anonymous_id
    rating_response     TINYINT NULL,                     -- 1-5 : "La réponse vous convient-elle ?"
    rating_relevance    TINYINT NULL,                     -- 1-5 : "Les documents fournis sont-ils pertinents ?"
    rating_formulation  TINYINT NULL,                     -- 1-5 : "Êtes-vous satisfait de la formulation ?"
    comment             TEXT NULL,                        -- commentaire libre, non modéré
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_cbf_message (message_id),               -- un seul feedback par message
    FOREIGN KEY (message_id) REFERENCES chatbot_messages(message_id) ON DELETE CASCADE,
    INDEX idx_cbf_user (user_id, created_at),
    INDEX idx_cbf_created (created_at),
    CONSTRAINT chk_cbf_rating_response    CHECK (rating_response    IS NULL OR rating_response    BETWEEN 1 AND 5),
    CONSTRAINT chk_cbf_rating_relevance   CHECK (rating_relevance   IS NULL OR rating_relevance   BETWEEN 1 AND 5),
    CONSTRAINT chk_cbf_rating_formulation CHECK (rating_formulation IS NULL OR rating_formulation BETWEEN 1 AND 5)
);
