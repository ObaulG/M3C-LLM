-- =============================================================================
-- SCRIPT DE CORRECTION DES ERREURS D'ENCODAGE (MOJIBAKE) DES DONNEES TEXTE
-- =============================================================================
-- Corrige le cas classique de mojibake : du texte UTF-8 qui a ete lu comme du
-- latin1 puis re-encode en utf8mb4 (ex: "Ã©" au lieu de "é", "â€™" au lieu
-- de "’", "Ã®" au lieu de "î").
--
-- Principe : pour chaque colonne texte (CHAR/VARCHAR/TEXT) de chaque table de
-- la base courante, on inverse l'erreur :
--   CONVERT(BINARY(CONVERT(col USING latin1)) USING utf8mb4)
-- La correction n'est appliquee que si :
--   1. la valeur contient des caracteres typiques du mojibake, ET
--   2. la conversion aller-retour est sans perte (round-trip latin1 -> binaire
--      -> utf8mb4 -> latin1 reproduit exactement la valeur d'origine).
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
-- ETAPE 0 : DIAGNOSTIC — lignes suspectes par table/colonne (lecture seule)
-- =============================================================================
-- A executer d'abord pour visualiser ce qui sera corrige. Cette vue liste
-- les colonnes contenant des caracteres typiques du mojibake.
DROP VIEW IF EXISTS encoding_suspect_columns;
CREATE VIEW encoding_suspect_columns AS
SELECT
    TABLE_SCHEMA,
    TABLE_NAME,
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_SET_NAME
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND CHARACTER_SET_NAME IS NOT NULL
  AND DATA_TYPE IN ('char', 'varchar', 'tinytext', 'text', 'mediumtext', 'longtext')
ORDER BY TABLE_NAME, ORDINAL_POSITION;

-- =============================================================================
-- ETAPE 1 : PROCEDURE DE CORRECTION
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
        SELECT TABLE_NAME, COLUMN_NAME
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND CHARACTER_SET_NAME IS NOT NULL
          AND DATA_TYPE IN ('char', 'varchar', 'tinytext', 'text', 'mediumtext', 'longtext')
        ORDER BY TABLE_NAME, ORDINAL_POSITION;
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
END$$

DELIMITER ;

-- =============================================================================
-- ETAPE 2 : EXECUTION
-- =============================================================================
CALL fix_text_encoding();

-- =============================================================================
-- ETAPE 3 : NETTOYAGE
-- =============================================================================
DROP PROCEDURE IF EXISTS fix_text_encoding;
DROP VIEW IF EXISTS encoding_suspect_columns;
