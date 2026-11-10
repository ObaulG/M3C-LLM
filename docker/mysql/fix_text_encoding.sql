-- =============================================================================
-- SCRIPT DE CORRECTION DES ERREURS D'ENCODAGE (MOJIBAKE) DES DONNEES TEXTE
-- =============================================================================
-- Corrige le cas classique de mojibake : du texte UTF-8 qui a ete lu comme du
-- latin1 puis re-encode en utf8mb4 (ex: "Ã©" au lieu de "é", "â€™" au lieu
-- de "’", "Ã®" au lieu de "î").
--
-- Principe : pour chaque colonne texte (CHAR/VARCHAR/TEXT) des tables du
-- projet (tous les fichiers .sql du depot, liste reprise ci-dessous), on
-- inverse l'erreur :
--   CONVERT(BINARY(CONVERT(col USING latin1)) USING utf8mb4)
-- La correction n'est appliquee que si :
--   1. la valeur contient des caracteres typiques du mojibake, ET
--   2. tous les caracteres de la valeur sont representables en latin1
--      (conversion latin1 -> utf8mb4 sans perte), ET
--   3. les octets latin1 resultant forment de l'UTF-8 valide (la correction
--      produira donc du texte reellement lisible).
-- Le script est donc idempotent et sans risque pour les donnees saines.
-- Limite connue : une ligne melant mojibake et caracteres non latin1
-- (ex: apostrophe typographique “’”) n'est pas modifiee, par securite.
--
-- Utilisation :
--   mysql -h <host> -u OBL -p m3c_database < fix_text_encoding.sql
--
-- RECOMMANDATION : faire une sauvegarde avant execution (mysqldump).
-- =============================================================================

SET NAMES utf8mb4;
SET SQL_MODE = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION';

-- =============================================================================
-- ETAPE 0 : TABLES CIBLES
-- =============================================================================
-- Seules les tables definies dans les fichiers SQL du projet sont ciblees.
-- Source : tous les fichiers .sql du projet (docker/mysql/, app/database/sql_tables_scripts/,
-- app/question_answer/tables.sql).
-- Si une nouvelle table est ajoutee a ces fichiers, l'ajouter aussi ici.
DROP TABLE IF EXISTS encoding_target_tables;
CREATE TABLE encoding_target_tables (
    table_name VARCHAR(64) PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO encoding_target_tables (table_name) VALUES
    ('answers'),
    ('chatbot_feedbacks'),
    ('chatbot_message_chunks'),
    ('chatbot_messages'),
    ('chunk_embeddings'),
    ('document_reading_sessions'),
    ('documents'),
    ('entities'),
    ('evaluations'),
    ('indexing_jobs'),
    ('knowledge_item_entities'),
    ('knowledge_item_questions'),
    ('knowledge_items'),
    ('knowledge_item_themes'),
    ('knowledge_sources'),
    ('llm_interpretations'),
    ('model_evidences'),
    ('observation_payloads'),
    ('observations'),
    ('observation_targets'),
    ('questions'),
    ('question_session_questions'),
    ('question_sessions'),
    ('session_answers'),
    ('session_messages'),
    ('sessions'),
    ('text_answer_facts'),
    ('text_chunking_strategies'),
    ('text_chunks'),
    ('text_document_chunking_validation'),
    ('text_documents'),
    ('text_question_answers'),
    ('text_question_chunks'),
    ('text_questions'),
    ('themes'),
    ('user'),
    ('user_interests_entities'),
    ('user_interests_themes'),
    ('user_knowledge_states'),
    ('user_mistral_api_keys'),
    ('user_model_history'),
    ('user_profiles'),
    ('user_sessions');

-- =============================================================================
-- ETAPE 1 : DIAGNOSTIC — colonnes texte des tables cibles (lecture seule)
-- =============================================================================
-- A executer d'abord pour visualiser ce qui sera corrige. Cette vue liste
-- les colonnes texte des tables cibles.
DROP VIEW IF EXISTS encoding_suspect_columns;
CREATE VIEW encoding_suspect_columns AS
SELECT
    c.TABLE_SCHEMA,
    c.TABLE_NAME,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.CHARACTER_SET_NAME
FROM information_schema.COLUMNS c
JOIN encoding_target_tables t ON t.table_name = c.TABLE_NAME
WHERE c.TABLE_SCHEMA = DATABASE()
  AND c.CHARACTER_SET_NAME IS NOT NULL
  AND c.DATA_TYPE IN ('char', 'varchar', 'tinytext', 'text', 'mediumtext', 'longtext')
ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;

-- =============================================================================
-- ETAPE 2 : PROCEDURE DE CORRECTION
-- =============================================================================
DROP PROCEDURE IF EXISTS fix_text_encoding;

DELIMITER $$

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
          AND c.DATA_TYPE IN ('char', 'varchar', 'tinytext', 'text', 'mediumtext', 'longtext')
        ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
    BEGIN
        -- Ne pas interrompre le script si une table est verrouillee :
        -- on signale et on continue avec la suivante.
        SELECT CONCAT('AVERTISSEMENT : erreur sur ',
                      v_table, '.', v_column) AS warning_message;
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
            -- (a) tous les caracteres representables en latin1
            --     (comparaison BINARY : insensible a la collation de la table,
            --     utf8mb4_unicode_ci sur les tables M3C vs utf8mb4_0900_ai_ci ailleurs)
            '  AND BINARY(`', v_column, '`) = BINARY(CONVERT(CONVERT(`', v_column,
            '` USING latin1) USING utf8mb4)) ',
            -- (b) les octets latin1 forment de l'UTF-8 valide
            '  AND BINARY(CONVERT(`', v_column, '` USING latin1)) = ',
            'BINARY(CONVERT(BINARY(CONVERT(`', v_column,
            '` USING latin1)) USING utf8mb4))'
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
END$$

DELIMITER ;

-- =============================================================================
-- ETAPE 3 : EXECUTION
-- =============================================================================
CALL fix_text_encoding();

-- =============================================================================
-- ETAPE 4 : NETTOYAGE
-- =============================================================================
DROP PROCEDURE IF EXISTS fix_text_encoding;
DROP VIEW IF EXISTS encoding_suspect_columns;
DROP TABLE IF EXISTS encoding_target_tables;
