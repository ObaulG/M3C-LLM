import json
from database import Database
from models_db import Chunk, Document

if __name__ == "__main__":
    db = Database("postgresql://user:password@localhost/dbname")

    # 1. Ajouter un document (exemple)
    document_id = "0ad4f240cfe1f7f90c243745769ef84326a1b60f.pdf"
    db.add_document(Document(
        document_id=document_id,
        file_name="mon_livre.pdf",
        file_path="/data/mon_livre.pdf",
        file_size=1024
    ))

    # 2. Ajouter une stratégie de découpage (ex: "800_tokens")
    strategy_id = 1  # À adapter selon ton ID de stratégie

    # 3. Lire le fichier JSON et ajouter les chunks
    with open("chunks.json", "r") as f:
        data = json.load(f)
        for chunk_key, chunk_data in data["chunks"].items():
            chunk = Chunk(
                chunk_id=chunk_key,
                document_id=document_id,
                strategy_id=strategy_id,
                content=chunk_data["content"],
                num_page=chunk_data["num_page"],
                token_count=len(chunk_data["content"].split()),  # Exemple simplifié
                metadata={"chapter": "1", "title": "Introduction"}  # À adapter
            )
            db.add_chunk(chunk)
