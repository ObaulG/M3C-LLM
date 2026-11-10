"""
Suppression des chunks dupliqués dans Qdrant.

Les points d'une collection "LD-*" portent l'identifiant unique du chunk
dans leur payload (clé "chunk_id"). Si une même ressource a été indexée
plusieurs fois, plusieurs points partagent le même "chunk_id" (avec des
IDs de point différents). Ce script itère sur tous les points de la
collection, conserve une seule occurrence par "chunk_id" et supprime
les autres.

Utilisation :
    python qdrant_delete_duplicate_chunks.py [--collection NOM] [--dry-run]

    --collection   Nom de la collection Qdrant
                   (défaut : LD-mistral-mistral-embed-1024)
    --dry-run      Liste les doublons sans rien supprimer
"""

import argparse
import os
from collections import defaultdict

from qdrant_client import QdrantClient
from qdrant_client.http import models

DEFAULT_COLLECTION = "LD-mistral-mistral-embed-1024"
BATCH_SIZE = 256
DELETE_BATCH_SIZE = 512


def parse_args():
    parser = argparse.ArgumentParser(
        description="Supprime les chunks dupliqués (même payload chunk_id) dans Qdrant."
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


def main():
    args = parse_args()

    client = QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
    )

    # chunk_id -> liste des IDs de points qui le portent
    points_by_chunk_id = defaultdict(list)

    print(f"Collection : {args.collection}")
    print("Lecture des points...")

    next_offset = None
    total_scanned = 0
    while True:
        points, next_offset = client.scroll(
            collection_name=args.collection,
            limit=BATCH_SIZE,
            with_payload=True,
            with_vectors=False,
            offset=next_offset,
        )
        if not points:
            break

        for point in points:
            payload = point.payload or {}
            chunk_id = payload.get("chunk_id")
            if chunk_id is None:
                print(f"  ⚠️  Point {point.id} sans chunk_id dans le payload, ignoré.")
                continue
            points_by_chunk_id[str(chunk_id)].append(point.id)
            total_scanned += 1

        if next_offset is None:
            break

    # Pour chaque chunk_id, conserver la première occurrence (la plus ancienne
    # dans l'ordre de scroll), marquer les autres pour suppression.
    duplicate_ids = []
    for chunk_id, point_ids in points_by_chunk_id.items():
        if len(point_ids) > 1:
            duplicate_ids.extend(point_ids[1:])

    print(f"Points scannés : {total_scanned}")
    print(f"Chunks uniques  : {len(points_by_chunk_id)}")
    print(f"Doublons à supprimer : {len(duplicate_ids)}")

    if not duplicate_ids:
        print("✅ Aucun doublon détecté.")
        return

    if args.dry_run:
        print("\n--dry-run : aucun point supprimé. Exemples de doublons :")
        shown = 0
        for chunk_id, point_ids in points_by_chunk_id.items():
            if len(point_ids) > 1 and shown < 10:
                print(f"  chunk_id={chunk_id} -> points conservés/supprimés : "
                      f"{point_ids[0]} / {point_ids[1:]}")
                shown += 1
        return

    print("Suppression des doublons...")
    deleted = 0
    for i in range(0, len(duplicate_ids), DELETE_BATCH_SIZE):
        batch = duplicate_ids[i:i + DELETE_BATCH_SIZE]
        client.delete(
            collection_name=args.collection,
            points_selector=models.PointIdsList(points=batch),
        )
        deleted += len(batch)
        print(f"  {deleted}/{len(duplicate_ids)} supprimés")

    print(f"✅ {deleted} doublons supprimés.")


if __name__ == "__main__":
    main()
