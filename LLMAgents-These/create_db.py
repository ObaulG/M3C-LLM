from sqlite3 import OperationalError
import traceback
import psycopg

# Configuration de la connexion
db_params = {
    "host": "localhost",
    "dbname": "mediationllm",
    "user": "postgres",
    "password": "postgres",
}


if __name__ == "__main__":
    with open("create_tables.sql", "r", encoding="utf-8") as f:
        sql_script = f.read()
    try:
        with psycopg.connect(**db_params) as conn:
            print("connected")
            with conn.cursor() as cur:
                cur.execute(sql_script)
                conn.commit()
        print("Base de données créée avec succès !")
    except Exception as e:
        print(f"Erreur : {e}")
    finally:
        if conn:
            conn.close()
