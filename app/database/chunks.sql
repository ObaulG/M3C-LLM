CREATE TABLE text_documents (
    id INT AUTO_INCREMENT PRIMARY KEY ,  -- Identifiant unique interne
    source_type VARCHAR(50) NOT NULL,  -- "pdf", "web_page", etc.
    source_id VARCHAR(255) NOT NULL,  -- ID externe (ex: ID du PDF dans la table pdfs, URL pour une page web)
    content TEXT NOT NULL,  -- Contenu textuel extrait
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_type, source_id)  -- Évite les doublons pour une même source
);

CREATE TABLE text_chunking_strategies (
    id INT AUTO_INCREMENT PRIMARY KEY ,
    name VARCHAR(255) NOT NULL,                -- Nom de la stratégie (ex: "800_tokens_overlap_100")
    description TEXT,                          -- Description de la stratégie
    method VARCHAR(50) NOT NULL,               -- Méthode de découpage : "tokens", "sentence", "paragraph", "page", "chapter"
    chunk_size INT,                            -- Taille du chunk (pour les méthodes "tokens" ou "sentence")
    char_size INT,
    overlap INT,                               -- Taille de l'overlap (pour les méthodes "tokens", "character ou "sentence")
    created_at TIMESTAMP DEFAULT NOW(),        -- Date de création
    CONSTRAINT unique_strategy_name UNIQUE (name)
);

CREATE TABLE text_chunks (
    id VARCHAR(255) PRIMARY KEY,
    document_id INT NOT NULL,
    strategy_id INT NOT NULL,
    content TEXT NOT NULL,
    num_page INT,
    position_in_page INT,
    token_count INT,
    character_count INT,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (document_id) REFERENCES text_documents(id),
    FOREIGN KEY (strategy_id) REFERENCES text_chunking_strategies(id)
);

CREATE TABLE text_document_chunking_validation (
    document_id INT NOT NULL,
    strategy_id INT NOT NULL,
    chunks_nb INT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES text_documents(id),
    FOREIGN KEY (strategy_id) REFERENCES text_chunking_strategies(id)
)