import os
import hashlib
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Configuration Qdrant
QDRANT_CONFIG = {
    "host": os.getenv("QDRANT_HOST", "localhost"),
    "port": int(os.getenv("QDRANT_PORT", "6333")),
}

# Nom de la collection
COLLECTION_NAME = "LD-mistral-mistral-embed-1024"  # Remplace par le nom de ta collection

def get_content_hash(content):
    """Calcule un hash SHA-256 pour le contenu."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def main():
    # Initialisation du client Qdrant
    client = QdrantClient(host=QDRANT_CONFIG["host"], port=QDRANT_CONFIG["port"])

    # Dictionnaire pour stocker les hashs et les IDs des points
    content_hashes = {}
    duplicate_ids = []

    # Récupération de tous les points par batches
    next_offset = None
    batch_size = 100  # Ajuste selon la taille de ta collection

    while True:
        points, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=batch_size,
            with_payload=True,
            with_vectors=False,
            offset=next_offset,
        )

        if not points:
            break  # Plus de points à traiter

        for point in points:
            content = point.payload.get("content", "")
            content_hash = get_content_hash(content)

            if content_hash in content_hashes:
                # Ce contenu est un doublon
                duplicate_ids.append(point.id)
            else:
                # Premier occurrence de ce contenu
                content_hashes[content_hash] = point.id

        if next_offset is None:
            break  # Fin de la collection

    # Suppression des doublons
    if duplicate_ids:
        print(f"🗑️ {len(duplicate_ids)} doublons détectés. Suppression en cours...")
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.PointIdsList(
                points=duplicate_ids,
            ),
        )
        print(f"✅ {len(duplicate_ids)} doublons supprimés.")
    else:
        print("✅ Aucun doublon détecté.")

if __name__ == "__main__":
    main()