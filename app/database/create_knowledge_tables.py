import os
import asyncio
from pathlib import Path

import aiomysql

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "db": os.getenv("DB_NAME", "m3c_database"),
    "user": os.getenv("DB_USER", "OBL"),
    "password": os.getenv("DB_PASSWORD", "azerty"),
    "autocommit": True
}

async def run_sql_file(filename: str) -> None:
    sql_script = Path(filename).read_text(encoding="utf-8")

    conn = await aiomysql.connect(**DB_CONFIG)

    try:
        print("Connecté à MySQL")

        async with conn.cursor() as cursor:
            await cursor.execute(sql_script)

            # Consomme les éventuels résultats des instructions suivantes.
            while await cursor.nextset():
                pass

        await conn.commit()
        print("Script SQL exécuté avec succès !")

    except Exception:
        await conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_sql_file("user_knowledge_model.sql"))
    except Exception as error:
        print(f"Erreur : {error}")