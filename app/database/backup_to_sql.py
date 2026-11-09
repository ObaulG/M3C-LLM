"""
Sauvegarde SQL de la base MySQL.

Exporte, pour toutes les tables decrites dans les fichiers SQL de
`sql_tables_scripts/`, le schema (SHOW CREATE TABLE) et le contenu
(INSERT INTO ...) dans un fichier .sql horodaté, réimportable via
mysql < fichier.sql ou exec_sql.py.

Utilisation :
    python backup_to_sql.py [--output-dir backups] [--tables tables.sql]
"""

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path

import aiomysql

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "db": os.getenv("DB_NAME", "m3c_database"),
    "user": os.getenv("DB_USER", "OBL"),
    "password": os.getenv("DB_PASSWORD", "azerty"),
    "autocommit": True,
}

SCRIPT_DIR = Path(__file__).resolve().parent
SQL_SCRIPTS_DIR = SCRIPT_DIR / "sql_tables_scripts"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "backups"

CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?([A-Za-z0-9_]+)`?",
    re.IGNORECASE,
)

INSERT_BATCH_SIZE = 500


def discover_tables(sql_scripts_dir: Path = SQL_SCRIPTS_DIR) -> list[str]:
    """Extrait, dans l'ordre des fichiers, les noms de tables declares
    dans les scripts SQL du projet."""
    tables: list[str] = []
    for sql_file in sorted(sql_scripts_dir.glob("*.sql")):
        content = sql_file.read_text(encoding="utf-8")
        for match in CREATE_TABLE_RE.finditer(content):
            name = match.group(1)
            if name not in tables:
                tables.append(name)
    return tables


def format_value(value, conn) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return conn.escape(value)


async def dump_table(cursor, conn, table: str, out) -> None:
    out.write(f"\n--\n-- Structure de la table `{table}`\n--\n\n")

    await cursor.execute(f"SHOW CREATE TABLE `{table}`")
    create_stmt = (await cursor.fetchone())[1]
    out.write(f"DROP TABLE IF EXISTS `{table}`;\n")
    out.write(create_stmt + ";\n")

    await cursor.execute(f"SELECT * FROM `{table}`")
    columns = [desc[0] for desc in cursor.description]
    rows = await cursor.fetchall()

    out.write(f"\n--\n-- Données de la table `{table}` ({len(rows)} ligne(s))\n--\n\n")
    if not rows:
        return

    column_list = ", ".join(f"`{c}`" for c in columns)
    insert_prefix = f"INSERT INTO `{table}` ({column_list}) VALUES\n"

    batch: list[str] = []
    for row in rows:
        values = ", ".join(format_value(v, conn) for v in row)
        batch.append(f"({values})")
        if len(batch) >= INSERT_BATCH_SIZE:
            out.write(insert_prefix + ",\n".join(batch) + ";\n")
            batch = []
    if batch:
        out.write(insert_prefix + ",\n".join(batch) + ";\n")


async def backup(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    tables: list[str] | None = None,
    sql_scripts_dir: Path = SQL_SCRIPTS_DIR,
) -> Path:
    if tables is None:
        tables = discover_tables(sql_scripts_dir)
    if not tables:
        raise RuntimeError(
            f"Aucune table trouvée dans les scripts SQL de {sql_scripts_dir}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"backup_{DB_CONFIG['db']}_{timestamp}.sql"

    conn = await aiomysql.connect(**DB_CONFIG)
    try:
        async with conn.cursor() as cursor:
            await cursor.execute("SHOW TABLES")
            existing_tables = {row[0] for row in await cursor.fetchall()}

        missing = [t for t in tables if t not in existing_tables]
        if missing:
            print(f"Tables absentes de la base (ignorées) : {', '.join(missing)}")

        with output_file.open("w", encoding="utf-8") as out:
            out.write(f"-- Sauvegarde MySQL de `{DB_CONFIG['db']}`\n")
            out.write(f"-- Générée le {datetime.now().isoformat()}\n")
            out.write("\nSET NAMES utf8mb4;\n")
            out.write("SET FOREIGN_KEY_CHECKS = 0;\n")
            out.write("SET UNIQUE_CHECKS = 0;\n")

            async with conn.cursor() as cursor:
                for table in tables:
                    if table not in existing_tables:
                        continue
                    print(f"Sauvegarde de `{table}`...")
                    await dump_table(cursor, conn, table, out)

            out.write("\nSET FOREIGN_KEY_CHECKS = 1;\n")
            out.write("SET UNIQUE_CHECKS = 1;\n")

    finally:
        conn.close()

    print(f"Sauvegarde terminée : {output_file}")
    return output_file


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Sauvegarde SQL (schéma + données) des tables du projet."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Répertoire de sortie (défaut : {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--tables",
        nargs="*",
        default=None,
        help="Tables à sauvegarder (défaut : toutes celles des scripts SQL)",
    )
    args = parser.parse_args()

    asyncio.run(backup(output_dir=args.output_dir, tables=args.tables))
