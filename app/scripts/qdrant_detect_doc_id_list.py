import argparse
import json
import os

from qdrant_client import QdrantClient

# Configuration Qdrant
QDRANT_CONFIG = {
    "host": os.getenv("QDRANT_HOST", "localhost"),
    "port": int(os.getenv("QDRANT_PORT", "6333")),
}

# Champs à inspecter
FIELDS_TO_CHECK = ["document_id"]

def is_anomalous(value):
    """Détecte une valeur de type liste (ex: [31]) au lieu d'un scalaire."""
    return isinstance(value, list)

def main():
    parser = argparse.ArgumentParser(
        description="Détecte les points dont un champ du payload est une liste (anomalie de type)."
    )
    parser.add_argument("collection", help="Nom de la collection à inspecter")
    parser.add_argument(
        "--fields",
        nargs="+",
        default=FIELDS_TO_CHECK,
        help="Champs du payload à inspecter (défaut : document_id)",
    )
    parser.add_argument(
        "--output",
        help="Fichier JSON de sortie pour le rapport détaillé",
        default=None,
    )
    parser.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args()

    client = QdrantClient(host=QDRANT_CONFIG["host"], port=QDRANT_CONFIG["port"])

    total_points = 0
    anomalies = []

    next_offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=args.collection,
            limit=args.batch_size,
            with_payload=True,
            with_vectors=False,
            offset=next_offset,
        )

        if not points:
            break

        for point in points:
            total_points += 1
            for field in args.fields:
                value = point.payload.get(field)
                if is_anomalous(value):
                    anomalies.append(
                        {
                            "point_id": str(point.id),
                            "field": field,
                            "value": value,
                        }
                    )

        if next_offset is None:
            break

    # Rapport
    print(f"📊 Statistiques :")
    print(f"   - Collection inspectée : {args.collection}")
    print(f"   - Total des points traités : {total_points}")
    print(f"   - Points anomalies : {len(anomalies)}")
    for anomaly in anomalies:
        print(
            f"   ⚠️  point_id={anomaly['point_id']} "
            f"champ={anomaly['field']} valeur={anomaly['value']}"
        )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "collection": args.collection,
                    "fields_checked": args.fields,
                    "total_points": total_points,
                    "anomaly_count": len(anomalies),
                    "anomalies": anomalies,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"   - Rapport écrit dans : {args.output}")

    if anomalies:
        print(
            "ℹ️  Pour corriger ces points, voir app/scripts/qdrant_correct_doc_id_list.py"
        )

if __name__ == "__main__":
    main()
