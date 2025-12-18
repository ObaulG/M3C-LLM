CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS chunking_strategies CASCADE;
DROP TABLE IF EXISTS chunks CASCADE;
DROP TABLE IF EXISTS chunk_embeddings CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS embedding_models CASCADE;

CREATE TABLE documents (
    document_id VARCHAR(255) PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    file_size INT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);


CREATE TABLE chunking_strategies (
    strategy_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,                -- Nom de la stratégie (ex: "800_tokens_overlap_100")
    description TEXT,                          -- Description de la stratégie
    method VARCHAR(50) NOT NULL,               -- Méthode de découpage : "tokens", "sentence", "paragraph", "page", "chapter"
    chunk_size INT,                            -- Taille du chunk (pour les méthodes "tokens" ou "sentence")
    overlap INT,                               -- Taille de l'overlap (pour les méthodes "tokens" ou "sentence")
    created_at TIMESTAMP DEFAULT NOW(),        -- Date de création
    CONSTRAINT valid_method CHECK (method IN ('tokens', 'sentence', 'paragraph', 'page', 'chapter')),
    CONSTRAINT unique_strategy_name UNIQUE (name)
);

CREATE TABLE chunks (
    chunk_id VARCHAR(255) PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    strategy_id INT NOT NULL,
    content TEXT NOT NULL,
    num_page INT,
    position_in_page INT,
    token_count INT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (document_id) REFERENCES documents(document_id),
    FOREIGN KEY (strategy_id) REFERENCES chunking_strategies(strategy_id)
);

CREATE TABLE embedding_models (
    model_name VARCHAR(255) PRIMARY KEY,
    description TEXT,
    dimension INT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE chunk_embeddings (
    embedding_id SERIAL PRIMARY KEY,
    chunk_id VARCHAR(255) NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    embedding VECTOR,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    FOREIGN KEY (model_name) REFERENCES embedding_models(model_name),
    UNIQUE (chunk_id, model_name)
);


CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_chunks_strategy ON chunks(strategy_id);
CREATE INDEX idx_chunks_page ON chunks(num_page);
CREATE INDEX idx_chunks_metadata ON chunks USING GIN (metadata jsonb_path_ops);
CREATE INDEX idx_chunking_strategies_method ON chunking_strategies(method);
