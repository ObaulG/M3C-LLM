import asyncio, aiomysql

TABLES = [
    'answers', 'chatbot_feedbacks', 'chatbot_message_chunks', 'chatbot_messages',
    'chunk_embeddings', 'document_reading_sessions', 'documents', 'entities',
    'evaluations', 'indexing_jobs', 'knowledge_item_entities', 'knowledge_item_questions',
    'knowledge_items', 'knowledge_item_themes', 'knowledge_sources', 'llm_interpretations',
    'model_evidences', 'observation_payloads', 'observations', 'observation_targets',
    'question_session_questions', 'question_sessions', 'questions',
    'session_answers', 'session_messages', 'sessions',
    'text_answer_facts', 'text_chunking_strategies', 'text_chunks',
    'text_document_chunking_validation', 'text_documents',
    'text_question_answers', 'text_question_chunks', 'text_questions', 'themes',
    'user', 'user_interests_entities', 'user_interests_themes',
    'user_knowledge_states', 'user_mistral_api_keys', 'user_model_history',
    'user_profiles', 'user_sessions',
    'value',   # table M3C (hors fichiers SQL du projet)
]

BATCH = 10_000  # lignes par lot — à réduire si besoin

GUARD = """
    `{col}` REGEXP 'Ã|Â|â€'
    AND BINARY(`{col}`) = BINARY(CONVERT(CONVERT(`{col}` USING latin1) USING utf8mb4))
    AND BINARY(CONVERT(`{col}` USING latin1)) =
        BINARY(CONVERT(BINARY(CONVERT(`{col}` USING latin1)) USING utf8mb4))
"""

async def main():
    conn = await aiomysql.connect(
        host="localhost", port=3306, db="m3c_database",
        user="OBL", password="azerty", charset="utf8mb4", autocommit=True,
    )
    cur = await conn.cursor()
    grand_total = 0

    for table in TABLES:
        # colonne de clé primaire (pour le batching)
        await cur.execute("""
            SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
              AND CONSTRAINT_NAME = 'PRIMARY' ORDER BY ORDINAL_POSITION LIMIT 1
        """, (table,))
        row = await cur.fetchone()
        if not row:
            print(f"Ignoré : {table} (pas de clé primaire)")
            continue
        pk = row[0]

        # colonnes texte de la table
        await cur.execute("""
            SELECT COLUMN_NAME FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
              AND CHARACTER_SET_NAME IS NOT NULL
              AND DATA_TYPE IN ('char','varchar','tinytext','text','mediumtext','longtext')
        """, (table,))
        columns = [r[0] for r in await cur.fetchall()]
        if not columns:
            continue

        # bornes d'id
        await cur.execute(f"SELECT MIN(`{pk}`), MAX(`{pk}`) FROM `{table}`")
        lo, hi = await cur.fetchone()
        if lo is None:
            continue

        for col in columns:
            fixed = 0
            start = lo
            while start <= hi:
                end = start + BATCH - 1
                sql = f"""
                    UPDATE `{table}` SET `{col}` =
                        CONVERT(BINARY(CONVERT(`{col}` USING latin1)) USING utf8mb4)
                    WHERE `{pk}` BETWEEN {start} AND {end}
                      AND `{col}` IS NOT NULL AND {GUARD.format(col=col)}
                """
                await cur.execute(sql)
                fixed += cur.rowcount
                start = end + 1
            if fixed:
                print(f"Corrigé : {table}.{col} — {fixed} ligne(s)")
                grand_total += fixed

    conn.close()
    print(f"Terminé. Total lignes corrigées : {grand_total}")

asyncio.run(main())