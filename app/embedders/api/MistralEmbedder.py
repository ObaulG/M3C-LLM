# embedders/api/mistral.py
from app.embedders.BaseEmbedder import BaseEmbedder
from typing import List
import os
import json
import tempfile
from mistralai import Mistral


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

    def create_batch_job(self, texts: List[str], custom_ids: List[str]) -> str:
        """Crée un job Batch API d'embeddings et retourne son identifiant.

        Les requêtes sont écrites dans un fichier JSONL (une requête par ligne,
        format {"custom_id": ..., "body": {"input": ...}}) puis uploadées via
        l'API Files : la soumission inline des requêtes est réservée aux petits
        volumes et échoue en 400 sur de grosses charges (ex. 42 000 textes).

        L'identifiant du job doit être persisté par l'appelant pour permettre la
        récupération des résultats plus tard (GET du statut + téléchargement
        du fichier de sortie, disponible 24 h après la complétion).

        Args:
            texts: Liste de textes à embedder.
            custom_ids: Identifiants (ex. resource_id) associés à chaque texte,
                retournés dans le fichier de résultats comme custom_id.

        Returns:
            L'identifiant du job batch créé.
        """
        if not texts:
            raise ValueError("Aucun texte à soumettre au job batch")
        if len(texts) != len(custom_ids):
            raise ValueError("texts et custom_ids doivent avoir la même longueur")

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
            ) as tmp:
                tmp_path = tmp.name
                for custom_id, text in zip(custom_ids, texts):
                    tmp.write(json.dumps(
                        {"custom_id": str(custom_id), "body": {"input": text}},
                        ensure_ascii=False,
                    ) + "\n")

            with Mistral(api_key=self._api_key) as mistral:
                with open(tmp_path, "rb") as f:
                    uploaded = mistral.files.upload(
                        file={"file_name": "metadata-embeddings.jsonl", "content": f},
                        purpose="batch",
                    )
                job = mistral.batch.jobs.create(
                    input_files=[uploaded.id],
                    endpoint="/v1/embeddings",
                    model=self.model,
                )
                return job.id
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def get_batch_job_status(self, batch_job_id: str) -> dict:
        """Retourne le statut courant d'un job Batch API.

        Returns:
            Dict avec les champs id, status (QUEUED, RUNNING, SUCCESS, FAILED,
            CANCELLED), output_file et errors_file du job.
        """
        with Mistral(api_key=self._api_key) as mistral:
            job = mistral.batch.jobs.get(job_id=batch_job_id)
            return {
                "id": job.id,
                "status": job.status,
                "output_file": job.output_file,
                "errors_file": getattr(job, "errors_file", None),
            }

    def iter_batch_results(self, batch_job_id: str):
        """Itère sur le fichier de résultats d'un job Batch API complété.

        Le fichier JSONL est parsé ligne par ligne sans charger la totalité
        des embeddings en mémoire.

        Args:
            batch_job_id: L'identifiant du job batch (statut SUCCESS).

        Yields:
            Tuples (custom_id, embedding, error) : embedding est None si la
            requête a échoué, auquel cas error contient le message.
        """
        with Mistral(api_key=self._api_key) as mistral:
            job = mistral.batch.jobs.get(job_id=batch_job_id)
            if job.status != "SUCCESS" or not job.output_file:
                raise Exception(f"Job Batch API {batch_job_id} terminé avec le statut {job.status}")

            output = mistral.files.download(file_id=job.output_file)
            if isinstance(output, (bytes, bytearray)):
                content = bytes(output)
            else:
                read = getattr(output, "read", None)
                if callable(read):
                    content = read()
                else:
                    content = output.content

        for raw_line in content.splitlines():
            line = raw_line.decode("utf-8", "replace") if isinstance(raw_line, bytes) else raw_line
            if not line.strip():
                continue
            result = json.loads(line)
            custom_id = result.get("custom_id")
            response = result.get("response") or {}
            status_code = response.get("status_code")
            if result.get("error") is not None or (status_code is not None and status_code >= 400):
                yield custom_id, None, f"{result.get('error') or response.get('body')}"
                continue
            body = response.get("body") or {}
            data = (body.get("data") or [{}])[0]
            embedding = data.get("embedding")
            if embedding is None:
                yield custom_id, None, f"Résultat batch invalide: {line[:200]}"
                continue
            yield custom_id, embedding, None