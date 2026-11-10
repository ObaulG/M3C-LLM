"""
Suppression des chunks dupliqués dans Qdrant.

La table SQL `text_chunks` contient les chunks uniques. À l'issue
d'indexations répétées, la collection Qdrant "LD-*" contient plusieurs
points pour un même chunk : leurs payloads portent des valeurs
strictement identiques pour (document_id, num_page, position_in_page).

Ce script itère sur tous les points de la collection Qdrant :
- pour chaque clé (document_id, num_page, position_in_page), la première
  occurrence rencontrée est conservée, les suivantes sont supprimées ;
- le chunk_id du payload est vérifié dans la table SQL `text_chunks` ;
  les points dont le chunk n'existe pas en SQL sont signalés (et
  optionnellement supprimés avec --delete-orphans).

Utilisation :
    python qdrant_delete_duplicate_chunks.py [--collection NOM] [--dry-run] [--delete-orphans]

Connexion MySQL via les variables d'environnement habituelles :
    DB_HOST (localhost), DB_PORT (3306), DB_NAME (m3c_database),
    DB_USER (OBL), DB_PASSWORD (azerty)
Connexion Qdrant : QDRANT_HOST (localhost), QDRANT_PORT (6333)
"""

import argparse
import asyncio
import os

import aiomysql
from qdrant_client import QdrantClient
from qdrant_client.http import models

DEFAULT_COLLECTION = "LD-mistral-mistral-embed-1024"
SCROLL_BATCH_SIZE = 256
DELETE_BATCH_SIZE = 512


def parse_args():
    parser = argparse.ArgumentParser(
        description="Supprime dans Qdrant les chunks dupliqués "
                    "(même document_id + num_page + position_in_page)."
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION),
        help=f"Nom de la collection Qdrant (défaut : {DEFAULT_COLLECTION})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lister les doublons et orphelins sans rien supprimer",
    )
    parser.add_argument(
        "--delete-orphans",
        action="store_true",
        help="Supprimer aussi les points dont le chunk_id est absent de text_chunks",
    )
    return parser.parse_args()


async def fetch_sql_chunks():
    """Retourne (chunk_ids, chunk_keys) lus dans text_chunks.

    chunk_ids : ensemble des id de text_chunks
    chunk_keys : ensemble des tuples (document_id, num_page, position_in_page)
    """
    conn = await aiomysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        db=os.getenv("DB_NAME", "m3c_database"),
        user=os.getenv("DB_USER", "OBL"),
        password=os.getenv("DB_PASSWORD", "azerty"),
        charset="utf8mb4",
    )
    try:
        cur = await conn.cursor()
        await cur.execute(
            "SELECT id, document_id, num_page, position_in_page FROM text_chunks"
        )
        rows = await cur.fetchall()
        await cur.close()
    finally:
        conn.close()

    chunk_ids = set()
    chunk_keys = set()
    for chunk_id, document_id, num_page, position_in_page in rows:
        chunk_ids.add(str(chunk_id))
        chunk_keys.add((str(document_id), num_page, position_in_page))
    return chunk_ids, chunk_keys


def chunk_key(payload):
    """Clé d'unicité d'un chunk au sein d'un document, depuis le payload Qdrant."""
    return (
        str(payload.get("document_id")),
        payload.get("num_page"),
        payload.get("position_in_page"),
    )


def main():
    args = parse_args()

    client = QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
    )

    sql_chunk_ids, sql_chunk_keys = asyncio.run(fetch_sql_chunks())
    print(f"Chunks en SQL (text_chunks) : {len(sql_chunk_ids)}")

    print(f"\nCollection : {args.collection}")
    print("Lecture des points Qdrant...")

    seen_keys = {}
    duplicate_ids = []
    orphan_ids = []
    total_scanned = 0

    next_offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=args.collection,
            limit=SCROLL_BATCH_SIZE,
            with_payload=True,
            with_vectors=False,
            offset=next_offset,
        )
        if not points:
            break

        for point in points:
            payload = point.payload or {}
            total_scanned += 1

            key = chunk_key(payload)
            chunk_id = str(payload.get("chunk_id", ""))

            if key in seen_keys:
                # Doublon : même document, même page, même position
                duplicate_ids.append(point.id)
                continue

            seen_keys[key] = point.id

            if chunk_id not in sql_chunk_ids:
                # Chunk absent de la table SQL
                orphan_ids.append(point.id)

        if next_offset is None:
            break

    print(f"Points scannés : {total_scanned}")
    print(f"Chunks uniques conservés : {len(seen_keys)}")
    print(f"Doublons détectés : {len(duplicate_ids)}")
    print(f"Points sans chunk correspondant en SQL : {len(orphan_ids)}")

    if args.dry_run:
        print("\n--dry-run : aucun point supprimé.")
        return

    ids_to_delete = list(duplicate_ids)
    if args.delete_orphans:
        ids_to_delete.extend(orphan_ids)
    elif orphan_ids:
        print("(Orphelins conservés ; relancez avec --delete-orphans pour les supprimer)")

    if not ids_to_delete:
        print("✅ Rien à supprimer.")
        return

    print(f"\nSuppression de {len(ids_to_delete)} points...")
    deleted = 0
    for i in range(0, len(ids_to_delete), DELETE_BATCH_SIZE):
        batch = ids_to_delete[i:i + DELETE_BATCH_SIZE]
        client.delete(
            collection_name=args.collection,
            points_selector=models.PointIdsList(points=batch),
        )
        deleted += len(batch)
        print(f"  {deleted}/{len(ids_to_delete)} supprimés")

    print(f"✅ {deleted} points supprimés.")


if __name__ == "__main__":
    main()
