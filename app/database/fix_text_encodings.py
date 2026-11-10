import os

import pymysql  # ou: import mysql.connector

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "db": os.getenv("DB_NAME", "m3c_database"),
    "user": os.getenv("DB_USER", "OBL"),
    "password": os.getenv("DB_PASSWORD", "azerty"),
    "autocommit": True,
    "charset": "utf8mb4"
}

conn = pymysql.connect(**DB_CONFIG)
# mysql.connector:
# conn = mysql.connector.connect(host=..., user=..., password=..., database=...)

cur = conn.cursor()

# --- ETAPE 0 : tables cibles -----------------------------------------------
cur.execute("DROP TABLE IF EXISTS encoding_target_tables")
cur.execute("""
    CREATE TABLE encoding_target_tables (
        table_name VARCHAR(64) PRIMARY KEY
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
cur.execute("""
    INSERT INTO encoding_target_tables (table_name) VALUES
    ('text_question_answers'),('chatbot_feedbacks'),('chatbot_message_chunks'),
    ('chatbot_messages'),('chunk_embeddings'),('document_reading_sessions'),
    ('documents'),('entities'),('evaluations'),('indexing_jobs'),
    ('knowledge_item_entities'),('knowledge_item_questions'),
    ('knowledge_items'),('knowledge_item_themes'),('knowledge_sources'),
    ('llm_interpretations'),('model_evidences'),('observation_payloads'),
    ('observations'),('observation_targets'),('text_questions'),
    ('session_messages'),('sessions'),('text_chunking_strategies'),
    ('text_chunks'),('text_document_chunking_validation'),
    ('text_documents'),('themes'),('user_interests_entities'),
    ('user_interests_themes'),('user_knowledge_states'),
    ('user_mistral_api_keys'),('user_model_history'),
    ('user_profiles'),('user_sessions')
""")

# --- ETAPE 1 : procedure (ENVOYEE COMME UNE SEULE REQUETE, sans DELIMITER) ---
cur.execute("DROP PROCEDURE IF EXISTS fix_text_encoding")

cur.execute("""
CREATE PROCEDURE fix_text_encoding()
BEGIN
    DECLARE done INT DEFAULT 0;
    DECLARE v_table VARCHAR(64);
    DECLARE v_column VARCHAR(64);
    DECLARE v_affected INT DEFAULT 0;
    DECLARE v_total INT DEFAULT 0;
    DECLARE cur CURSOR FOR
        SELECT c.TABLE_NAME, c.COLUMN_NAME
        FROM information_schema.COLUMNS c
        JOIN encoding_target_tables t ON t.table_name = c.TABLE_NAME
        WHERE c.TABLE_SCHEMA = DATABASE()
          AND c.CHARACTER_SET_NAME IS NOT NULL
          AND c.DATA_TYPE IN ('char','varchar','tinytext','text','mediumtext','longtext')
        ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
    BEGIN
        SELECT CONCAT('AVERTISSEMENT : erreur sur ', v_table, '.', v_column) AS warning_message;
    END;

    OPEN cur;
    read_loop: LOOP
        FETCH cur INTO v_table, v_column;
        IF done THEN
            LEAVE read_loop;
        END IF;

        SET @sql = CONCAT(
            'UPDATE `', v_table, '` SET `', v_column, '` = ',
            'CONVERT(BINARY(CONVERT(`', v_column, '` USING latin1)) USING utf8mb4) ',
            'WHERE `', v_column, '` IS NOT NULL ',
            "  AND `", v_column, "` REGEXP 'Ã|Â|â€' ",
            '  AND `', v_column, '` = CONVERT(CONVERT(BINARY(CONVERT(`', v_column,
            '` USING latin1)) USING utf8mb4) USING latin1)'
        );
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        SET v_affected = ROW_COUNT();
        DEALLOCATE PREPARE stmt;

        IF v_affected > 0 THEN
            SELECT CONCAT('Corrigé : ', v_table, '.', v_column,
                          ' — ', v_affected, ' ligne(s)') AS fix_report;
            SET v_total = v_total + v_affected;
        END IF;
    END LOOP;
    CLOSE cur;

    SELECT CONCAT('Terminé. Total lignes corrigées : ', v_total) AS final_report;
END
""")

# --- ETAPE 2 : execution -----------------------------------------------------
cur.execute("CALL fix_text_encoding()")
for row in cur.fetchall():
    print(row)

# --- ETAPE 3 : nettoyage -------------------------------------------------------
cur.execute("DROP PROCEDURE IF EXISTS fix_text_encoding")
cur.execute("DROP VIEW IF EXISTS encoding_suspect_columns")
cur.execute("DROP TABLE IF EXISTS encoding_target_tables")

conn.commit()
cur.close()
conn.close()
print("Correction de l'encodage terminée.")