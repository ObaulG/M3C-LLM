-- V001: Tables initiales (documents, chunking strategies, chunks)

CREATE TABLE IF NOT EXISTS text_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE(source_type, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS text_chunking_strategies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    method VARCHAR(50) NOT NULL,
    chunk_size INT,
    char_size INT,
    overlap INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_strategy_name UNIQUE (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
    FOREIGN KEY (strategy_id) REFERENCES text_chunking_strategies(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
