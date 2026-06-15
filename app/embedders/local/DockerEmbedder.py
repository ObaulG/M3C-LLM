from app.embedders.BaseEmbedder import BaseEmbedder
from typing import List, Dict, Any
import requests
import time
import logging

logger = logging.getLogger(__name__)


class DockerEmbedder(BaseEmbedder):
    def __init__(
        self,
        model_name: str,
        api_endpoint: str,
        docker_config: Dict[str, Any],
        dimension: int,
        batch_size: int = 32,
        timeout: int = 30,
    ):
        self.model_name = model_name
        self.api_endpoint = api_endpoint
        self.docker_config = docker_config
        self.dimension = dimension
        self.batch_size = batch_size
        self.timeout = timeout

    @property
    def name(self) -> str:
        return f"docker-{self.model_name}"

    def ping(self) -> bool:
        """Vérifie que le conteneur Docker est en cours d'exécution et que l'API répond."""
        try:
            response = requests.get(f"{self.api_endpoint}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def embed(self, text: str) -> List[float]:
        """Embed un seul texte via l'API locale."""
        try:
            response = requests.post(
                f"{self.api_endpoint}/encode",
                json={"text": text},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except requests.RequestException as e:
            logger.error(f"Failed to embed text: {e}")
            raise

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed une liste de textes via l'API locale."""
        # Découpe en batchs si nécessaire
        embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            try:
                response = requests.post(
                    f"{self.api_endpoint}/encode/batch",
                    json={"texts": batch},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                embeddings.extend(response.json()["embeddings"])
            except requests.RequestException as e:
                logger.error(f"Failed to embed batch: {e}")
                raise
        return embeddings

    def dimension(self) -> int:
        return self.dimension