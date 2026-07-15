import os
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Configuration Qdrant
QDRANT_CONFIG = {
    "host": os.getenv("QDRANT_HOST", "localhost"),
    "port": int(os.getenv("QDRANT_PORT", "6333")),
}

# Nom de la collection à corriger
COLLECTION_NAME = "LD-mistral-mistral-embed-1024"  # Remplace par le nom de ta collection

# Champs à corriger (ajoute d'autres champs si nécessaire)
FIELDS_TO_FIX = ["document_id"]

def is_list_with_single_element(value):
    """Vérifie si la valeur est une liste avec un seul élément."""
    return isinstance(value, list) and len(value) == 1

def fix_payload(payload):
    """Corrige les champs spécifiés dans le payload."""
    fixed_payload = payload.copy()
    for field in FIELDS_TO_FIX:
        if field in fixed_payload and is_list_with_single_element(fixed_payload[field]):
            fixed_payload[field] = fixed_payload[field][0]
    return fixed_payload

def main():
    # Initialisation du client Qdrant
    client = QdrantClient(host=QDRANT_CONFIG["host"], port=QDRANT_CONFIG["port"])

    # Initialisation des statistiques
    total_points = 0
    corrected_points = 0
    skipped_points = 0

    # Récupération de tous les points par batches
    next_offset = None
    batch_size = 100  # Ajuste selon la taille de ta collection

    while True:
        points, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=batch_size,
            with_payload=True,
            with_vectors=True,
            offset=next_offset,
        )

        if not points:
            break  # Plus de points à traiter

        # Correction et mise à jour
        updated_points = []
        for point in points:
            total_points += 1
            fixed_payload = fix_payload(point.payload)
            if fixed_payload != point.payload:
                updated_points.append(
                    models.PointStruct(
                        id=point.id,
                        payload=fixed_payload,
                        vector=point.vector,
                    )
                )
                corrected_points += 1
            else:
                skipped_points += 1

        # Mise à jour par batch
        if updated_points:
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=updated_points,
                wait=True,
            )

        if next_offset is None:
            break  # Fin de la collection

    # Affichage des statistiques
    print(f"📊 Statistiques :")
    print(f"   - Total des points traités : {total_points}")
    print(f"   - Points corrigés : {corrected_points}")
    print(f"   - Points non modifiés : {skipped_points}")

if __name__ == "__main__":
    main()