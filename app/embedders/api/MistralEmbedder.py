# embedders/api/mistral.py
from app.embedders.BaseEmbedder import BaseEmbedder
from typing import List
import os
import json
import time
from mistralai import Mistral

# Statuts non terminaux d'un job Batch API
_BATCH_PENDING_STATUSES = {"QUEUED", "RUNNING"}


class MistralEmbedder(BaseEmbedder):
    supports_batch_api = True

    def __init__(self, api_key: str, model: str = "mistral-embed", dimension: int = 1024) -> None:
        self.model = model
        self.dimension = dimension
        self._api_key = api_key or os.getenv("MISTRAL_API_KEY", "")

    @property
    def name(self) -> str:
        return f"mistral-{self.model}"

    @property
    def model_id(self) -> str:
        return self.model

    def ping(self) -> bool:
        """Vérifie que l'API Mistral est accessible."""
        try:
            with Mistral(api_key=self._api_key) as mistral:
                # Essayer une requête simple pour vérifier la connexion
                mistral.embeddings.create(model=self.model, input="test", output_dimension=32)
                return True
        except Exception:
            return False

    def embed(self, text: str) -> List[float]:
        with Mistral(api_key=self._api_key) as mistral:
            response = mistral.embeddings.create(
                model=self.model, 
                inputs=[text],
            )
            # Extraire l'embedding de la réponse
            return response.data[0].embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        with Mistral(api_key=self._api_key) as mistral:
            try:
                response = mistral.embeddings.create(
                    model=self.model,
                    inputs=texts,
                )
            except Exception as e:
                print(e)
                raise Exception
            # Extraire les embeddings de la réponse
            return [item.embedding for item in response.data]

    def dimension(self) -> int:
        return self.dimension

    def embed_batch_api(self, texts: List[str], poll_interval: int = 10) -> List[List[float]]:
        """Embed une liste de textes via la Batch API Mistral (-50 % sur le coût).

        Crée un job batch inline (endpoint /v1/embeddings), attend sa complétion
        puis télécharge et parse le fichier de résultats JSONL.

        Args:
            texts: Liste de textes à embedder.
            poll_interval: Intervalle de polling du statut du job, en secondes.

        Returns:
            Liste d'embeddings dans le même ordre que les textes d'entrée.
        """
        if not texts:
            return []

        with Mistral(api_key=self._api_key) as mistral:
            requests = [
                {"custom_id": str(i), "body": {"input": text}}
                for i, text in enumerate(texts)
            ]
            job = mistral.batch.jobs.create(
                endpoint="/v1/embeddings",
                model=self.model,
                requests=requests,
            )

            while job.status in _BATCH_PENDING_STATUSES:
                time.sleep(poll_interval)
                job = mistral.batch.jobs.get(job_id=job.id)

            if job.status != "SUCCESS" or not job.output_file:
                raise Exception(f"Job Batch API {job.id} terminé avec le statut {job.status}")

            output = mistral.files.download(file_id=job.output_file)
            content = getattr(output, "content", None)
            if content is None:
                chunks = []
                stream = getattr(output, "stream", None) or output
                for chunk in stream:
                    chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8"))
                content = b"".join(chunks)

        embeddings_by_id = {}
        for line in content.splitlines():
            if not line.strip():
                continue
            result = json.loads(line)
            response = result.get("response") or {}
            data = (response.get("data") or [{}])[0]
            embedding = data.get("embedding")
            if embedding is None:
                raise Exception(f"Résultat batch invalide pour custom_id {result.get('custom_id')}")
            embeddings_by_id[result["custom_id"]] = embedding

        missing = [i for i in range(len(texts)) if str(i) not in embeddings_by_id]
        if missing:
            raise Exception(f"Embeddings manquants dans le résultat batch: {missing}")

        return [embeddings_by_id[str(i)] for i in range(len(texts))]