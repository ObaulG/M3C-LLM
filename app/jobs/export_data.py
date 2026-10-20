"""
Export des données du projet LLMAgents.

Ce script exporte :
  - Les données de la base MySQL (m3c_database) dans un fichier .sql contenant
    les INSERT des tables déclarées dans app/database/sql_tables_scripts/*.sql
    (CREATE TABLE uniquement ; les CREATE VIEW sont exclus). Le schéma (CREATE
    TABLE) n'est PAS inclus : il est supposé déjà créé par docker/mysql/init.sql.
    Les tables déclarées mais absentes de MySQL sont ignorées avec un
    avertissement (ex: scripts PostgreSQL du dossier).
  - Les collections Qdrant sous forme de snapshots natifs (.tar.gz) via l'API
    REST /collections/{name}/snapshots. Re-importables avec l'API Qdrant
    /collections/{name}/snapshots/upload ou la commande qdrant CLI.

Usage :
    python -m app.jobs.export_data                       # export MySQL + Qdrant
    python -m app.jobs.export_data --only mysql           # export MySQL seul
    python -m app.jobs.export_data --only qdrant          # export Qdrant seul
    python -m app.jobs.export_data --output-dir ./exports # répertoire cible

Configuration : variables d'environnement (cf. .env.example)
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
    QDRANT_HOST, QDRANT_PORT

Sortie :
    <output-dir>/mysql_data_<timestamp>.sql
    <output-dir>/qdrant_snapshots/<collection>_<timestamp>.tar.gz
"""
import argparse
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import aiomysql
import asyncio
import urllib.request
import urllib.error
import json


# Dossier contenant les fichiers .sql de déclaration des tables.
# La liste des tables à exporter est extraite de ces fichiers (CREATE TABLE
# uniquement ; les CREATE VIEW sont exclus).
SQL_TABLES_DIR = Path(__file__).resolve().parent.parent / "database" / "sql_tables_scripts"


# ---------------------------------------------------------------------------
# Configuration (identique à app/database/database.py)
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "db": os.getenv("DB_NAME", "m3c_database"),
    "user": os.getenv("DB_USER", "OBL"),
    "password": os.getenv("DB_PASSWORD", "azerty"),
}

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_URL = f"http://{QDRANT_HOST}:{QDRANT_PORT}"


# ---------------------------------------------------------------------------
# Export MySQL
# ---------------------------------------------------------------------------
# Regex pour extraire le nom de table d'un "CREATE TABLE [IF NOT EXISTS] nom".
# Capture le nom même s'il est entouré de backticks, guillemets ou rien.
_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?([a-zA-Z_][a-zA-Z0-9_]*)[`\"']?",
    re.IGNORECASE,
)


def list_declared_tables() -> List[str]:
    """Liste les tables déclarées dans les fichiers .sql du dossier
    app/database/sql_tables_scripts/. Les CREATE VIEW sont exclus.

    Retourne une liste triée et dédoublonnée.
    """
    if not SQL_TABLES_DIR.is_dir():
        raise FileNotFoundError(
            f"Dossier des scripts SQL introuvable : {SQL_TABLES_DIR}"
        )

    tables: set = set()
    for sql_file in sorted(SQL_TABLES_DIR.glob("*.sql")):
        text = sql_file.read_text(encoding="utf-8", errors="replace")
        # On ignore les CREATE VIEW en ne matchant que CREATE TABLE.
        for m in _CREATE_TABLE_RE.finditer(text):
            tables.add(m.group(1))
    return sorted(tables)


async def list_tables(conn) -> List[str]:
    """Retourne la liste des tables à exporter : celles déclarées dans les
    fichiers SQL de app/database/sql_tables_scripts/ ET présentes dans MySQL.
    Les tables déclarées mais absentes de MySQL sont signalées (ex: scripts
    PostgreSQL dont les tables n'existent pas en MySQL)."""
    declared = list_declared_tables()

    # Tables réellement présentes dans MySQL
    async with conn.cursor() as cur:
        await cur.execute("SHOW TABLES")
        rows = await cur.fetchall()
    existing = {r[0] for r in rows}

    result = []
    for t in declared:
        if t in existing:
            result.append(t)
        else:
            print(
                f"[MySQL] ATTENTION : table '{t}' déclarée dans "
                f"sql_tables_scripts mais absente de MySQL -> ignorée.",
                file=sys.stderr,
            )
    return result


def sql_escape(value) -> str:
    """Échappe une valeur Python pour un INSERT SQL MySQL."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (bytes, bytearray)):
        # Représentation hexadécimale MySQL : x'...'
        return "x'" + value.hex() + "'"
    # str et autres : échappement basique MySQL
    s = str(value)
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\\'")
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    s = s.replace("\x00", "\\0")
    return "'" + s + "'"


async def export_table(conn, table: str, out_file) -> int:
    """Exporte une table sous forme de INSERT INTO. Retourne le nombre de
    lignes écrites."""
    total = 0
    async with conn.cursor() as cur:
        await cur.execute(f"SELECT * FROM `{table}`")
        cols = [d[0] for d in cur.description]
        col_list = ", ".join(f"`{c}`" for c in cols)

        batch: List[str] = []
        BATCH_SIZE = 1000

        async for row in cur:
            values = ", ".join(sql_escape(v) for v in row)
            batch.append(f"({values})")
            total += 1

            if len(batch) >= BATCH_SIZE:
                out_file.write(
                    f"INSERT INTO `{table}` ({col_list}) VALUES\n"
                )
                out_file.write(",\n".join(batch))
                out_file.write(";\n\n")
                batch = []

        if batch:
            out_file.write(f"INSERT INTO `{table}` ({col_list}) VALUES\n")
            out_file.write(",\n".join(batch))
            out_file.write(";\n\n")

    return total


async def export_mysql(output_path: Path) -> dict:
    """Exporte toutes les tables de la base MySQL dans output_path.
    Retourne un récapitulatif {table: nb_lignes}."""
    print(f"[MySQL] Connexion à {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['db']} ...")
    conn = await aiomysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        db=DB_CONFIG["db"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        autocommit=True,
        charset="utf8mb4",
    )

    try:
        tables = await list_tables(conn)
        print(f"[MySQL] {len(tables)} tables trouvées : {', '.join(tables)}")

        recap = {}
        with open(output_path, "w", encoding="utf-8", newline="\n") as f:
            # En-tête
            f.write("-- ============================================================\n")
            f.write(f"-- Export des données MySQL - {datetime.now().isoformat()}\n")
            f.write(f"-- Base : {DB_CONFIG['db']}\n")
            f.write(f"-- Tables : {len(tables)}\n")
            f.write("-- Schéma NON inclus (voir docker/mysql/init.sql)\n")
            f.write("-- ============================================================\n\n")
            f.write("SET NAMES utf8mb4;\n")
            f.write("SET FOREIGN_KEY_CHECKS=0;\n")
            f.write(f"USE `{DB_CONFIG['db']}`;\n\n")

            for table in tables:
                print(f"[MySQL] Export de {table} ...", end=" ")
                n = await export_table(conn, table, f)
                recap[table] = n
                print(f"{n} lignes")

            f.write("\nSET FOREIGN_KEY_CHECKS=1;\n")
            f.write("-- Fin de l'export\n")

        return recap
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Export Qdrant (snapshots natifs)
# ---------------------------------------------------------------------------
def http_get(url: str, timeout: int = 60) -> bytes:
    """GET HTTP, retourne le contenu binaire."""
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_get_json(url: str, timeout: int = 30) -> dict:
    return json.loads(http_get(url, timeout).decode("utf-8"))


def http_post(url: str, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, method="POST", data=b"")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_qdrant_collections() -> List[str]:
    data = http_get_json(f"{QDRANT_URL}/collections")
    raw = data.get("result", {}).get("collections", [])
    # L'API Qdrant renvoie une liste de dicts {"name": "..."} ; on extrait le nom.
    names = []
    for item in raw:
        if isinstance(item, dict):
            name = item.get("name")
        else:
            name = item
        if name:
            names.append(name)
    return names


def export_qdrant_collection(collection: str, output_dir: Path, timestamp: str) -> Path:
    """Crée un snapshot d'une collection Qdrant et le télécharge.
    Retourne le chemin du fichier .tar.gz téléchargé."""
    print(f"[Qdrant] Création du snapshot pour '{collection}' ...")
    # POST /collections/{name}/snapshots crée un snapshot et renvoie son nom
    resp = http_post(f"{QDRANT_URL}/collections/{collection}/snapshots")
    snapshot_name = resp.get("result", {}).get("name")
    if not snapshot_name:
        raise RuntimeError(f"Impossible de créer le snapshot pour {collection}: {resp}")

    download_url = f"{QDRANT_URL}/collections/{collection}/snapshots/{snapshot_name}"
    print(f"[Qdrant] Téléchargement de {snapshot_name} ...")
    data = http_get(download_url, timeout=300)

    out_file = output_dir / f"{collection}_{timestamp}.tar.gz"
    out_file.write_bytes(data)
    print(f"[Qdrant] Sauvegardé : {out_file} ({len(data)} octets)")

    # Optionnel : supprimer le snapshot côté serveur pour ne pas encombrer
    try:
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{collection}/snapshots/{snapshot_name}",
            method="DELETE",
        )
        urllib.request.urlopen(req, timeout=30)
    except urllib.error.URLError:
        pass  # non bloquant

    return out_file


def export_qdrant(output_dir: Path, timestamp: str) -> List[Path]:
    """Exporte toutes les collections Qdrant en snapshots natifs."""
    print(f"[Qdrant] Connexion à {QDRANT_URL} ...")
    collections = list_qdrant_collections()
    print(f"[Qdrant] {len(collections)} collections : {', '.join(collections)}")

    snapshots_dir = output_dir / "qdrant_snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for collection in collections:
        try:
            f = export_qdrant_collection(collection, snapshots_dir, timestamp)
            files.append(f)
        except Exception as e:
            print(f"[Qdrant] ERREUR sur {collection}: {e}", file=sys.stderr)

    return files


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Export des données MySQL et Qdrant du projet LLMAgents."
    )
    parser.add_argument(
        "--only",
        choices=["mysql", "qdrant"],
        help="Exporter uniquement MySQL ou Qdrant (défaut: les deux).",
    )
    parser.add_argument(
        "--output-dir",
        default="./exports",
        help="Répertoire de sortie (défaut: ./exports).",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.only in (None, "mysql"):
        sql_path = output_dir / f"mysql_data_{timestamp}.sql"
        print(f"\n=== Export MySQL -> {sql_path} ===")
        recap = asyncio.run(export_mysql(sql_path))
        total_rows = sum(recap.values())
        print(f"\n[MySQL] Export terminé : {total_rows} lignes au total dans {sql_path}")

    if args.only in (None, "qdrant"):
        print(f"\n=== Export Qdrant -> {output_dir / 'qdrant_snapshots'} ===")
        files = export_qdrant(output_dir, timestamp)
        print(f"\n[Qdrant] Export terminé : {len(files)} snapshot(s) téléchargé(s).")

    print("\nPour ré-importer :")
    if args.only in (None, "mysql"):
        print(f"  MySQL : docker exec -i <conteneur_mysql> mysql -u{DB_CONFIG['user']} -p{DB_CONFIG['password']} {DB_CONFIG['db']} < {sql_path}")
    if args.only in (None, "qdrant"):
        print(f"  Qdrant : curl -X PUT http://{QDRANT_HOST}:{QDRANT_PORT}/collections/{{name}}/snapshots/upload -F 'file=@<snapshot.tar.gz>'")


if __name__ == "__main__":
    main()
