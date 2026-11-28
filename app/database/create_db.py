import asyncio
import os

import aiomysql

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "db": os.getenv("DB_NAME", "m3c_database"),
    "user": os.getenv("DB_USER", "OBL"),
    "password": os.getenv("DB_PASSWORD", "azerty"),
    "autocommit": True,
    "charset": "utf8mb4",
}


async def main() -> None:
    with open("create_tables_1st_iteration.sql", "r", encoding="utf-8") as f:
        sql_script = f.read()
    conn = await aiomysql.connect(**DB_CONFIG)
    try:
        async with conn.cursor() as cur:
            await cur.execute(sql_script)
            while await cur.nextset():
                pass
        print("Base de données créée avec succès !")
    except Exception as e:
        print(f"Erreur : {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    asyncio.run(main())
