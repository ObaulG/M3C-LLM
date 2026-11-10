"""
Suppression des chunks dupliqués dans la table MySQL `text_chunks`.

La base Qdrant contient les chunks uniques : chaque point porte dans son
payload l'identifiant du chunk (clé "chunk_id") ainsi que
(document_id, num_page, position_in_page). La table SQL `text_chunks`
contient quant à elle des doublons : plusieurs lignes partagent les mêmes
(document_id, num_page, position_in_page) au sein d'un document.

Ce script :
1. itère sur les points de la collection Qdrant pour récupérer les
   chunk_id référencés (les chunks valides) ;
2. lit la table `text_chunks` et regroupe les lignes par
   (document_id, num_page, position_in_page) ;
3. pour chaque groupe de lignes en double, conserve celle dont l'id est
   référencé dans Qdrant (ou la première si aucune ne l'est) et supprime
   les autres.

La suppression dans text_chunks cascade sur les tables qui la référencent
(ex: text_question_chunks, ON DELETE CASCADE).

Utilisation :
    python mysql_delete_duplicate_chunks.py [--collection NOM] [--dry-run]

Connexion MySQL via les variables d'environnement habituelles :
    DB_HOST (localhost), DB_PORT (3306), DB_NAME (m3c_database),
    DB_USER (OBL), DB_PASSWORD (azerty)
Connexion Qdrant : QDRANT_HOST (localhost), QDRANT_PORT (6333)
"""

import argparse
import asyncio
import os
from collections import defaultdict

import aiomysql
from qdrant_client import QdrantClient

DEFAULT_COLLECTION = "LD-mistral-mistral-embed-1024"
SCROLL_BATCH_SIZE = 256


def parse_args():
    parser = argparse.ArgumentParser(
        description="Supprime dans MySQL (text_chunks) les chunks dupliqués "
                    "(même document_id + num_page + position_in_page), "
                    "en s'appuyant sur les chunk_id référencés dans Qdrant."
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION),
        help=f"Nom de la collection Qdrant (défaut : {DEFAULT_COLLECTION})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lister les doublons sans les supprimer",
    )
    return parser.parse_args()


async def connect_mysql():
    return await aiomysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        db=os.getenv("DB_NAME", "m3c_database"),
        user=os.getenv("DB_USER", "OBL"),
        password=os.getenv("DB_PASSWORD", "azerty"),
        charset="utf8mb4",
    )


def fetch_qdrant_chunk_ids(client, collection_name):
    """Retourne l'ensemble des chunk_id référencés dans les payloads Qdrant."""
    chunk_ids = set()
    next_offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=collection_name,
            limit=SCROLL_BATCH_SIZE,
            with_payload=True,
            with_vectors=False,
            offset=next_offset,
        )
        if not points:
            break
        for point in points:
            payload = point.payload or {}
            chunk_id = payload.get("chunk_id")
            if chunk_id is not None:
                chunk_ids.add(str(chunk_id))
        if next_offset is None:
            break
    return chunk_ids


async def main():
    args = parse_args()

    qdrant_client = QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
    )

    print(f"Collection Qdrant : {args.collection}")
    print("Lecture des chunk_id référencés dans Qdrant...")
    qdrant_chunk_ids = fetch_qdrant_chunk_ids(qdrant_client, args.collection)
    print(f"Chunk_id uniques dans Qdrant : {len(qdrant_chunk_ids)}")

    conn = await connect_mysql()
    try:
        cur = await conn.cursor()

        await cur.execute(
            "SELECT id, document_id, num_page, position_in_page FROM text_chunks"
        )
        rows = await cur.fetchall()

        # key (document_id, num_page, position_in_page) -> liste des id de lignes
        rows_by_key = defaultdict(list)
        for chunk_id, document_id, num_page, position_in_page in rows:
            key = (str(document_id), num_page, position_in_page)
            rows_by_key[key].append(str(chunk_id))

        total_rows = len(rows)
        duplicate_keys = {k: ids for k, ids in rows_by_key.items() if len(ids) > 1}

        print(f"\nLignes dans text_chunks : {total_rows}")
        print(f"Clés uniques (document, page, position) : {len(rows_by_key)}")
        print(f"Clés en double : {len(duplicate_keys)}")

        # Pour chaque clé en double : conserver la ligne référencée dans
        # Qdrant (sinon la première), supprimer les autres.
        to_delete = []
        for key, ids in duplicate_keys.items():
            referenced = [i for i in ids if i in qdrant_chunk_ids]
            keep = referenced[0] if referenced else ids[0]
            to_delete.extend(i for i in ids if i != keep)

        # Lignes SQL dont l'id n'est référencé nulle part dans Qdrant
        orphans = [str(row_id) for row_id, *_ in rows
                   if str(row_id) not in qdrant_chunk_ids]

        print(f"Lignes à supprimer (doublons) : {len(to_delete)}")
        print(f"Lignes sans point Qdrant correspondant : {len(orphans)}")

        if args.dry_run:
            print("\n--dry-run : aucune ligne supprimée. Exemples :")
            shown = 0
            for key, ids in duplicate_keys.items():
                if shown >= 10:
                    break
                referenced = [i for i in ids if i in qdrant_chunk_ids]
                keep = referenced[0] if referenced else ids[0]
                print(f"  doc={key[0]} page={key[1]} position={key[2]} : "
                      f"conservé {keep}, supprimés {[i for i in ids if i != keep]}")
                shown += 1
            await cur.close()
            return

        if not to_delete:
            print("✅ Aucun doublon à supprimer.")
            await cur.close()
            return

        print(f"\nSuppression de {len(to_delete)} lignes dans text_chunks...")
        placeholders = ", ".join(["%s"] * len(to_delete))
        await cur.execute(
            f"DELETE FROM text_chunks WHERE id IN ({placeholders})",
            to_delete,
        )
        await conn.commit()
        print(f"✅ {cur.rowcount} doublons supprimés de text_chunks "
              "(les tables liées sont mises à jour via ON DELETE CASCADE).")

        await cur.close()
    finally:
        conn.close()


if __name__ == "__main__":
    asyncio.run(main())
