from embedders.base import BaseEmbedder
from typing import List, Dict, Any
import requests
import docker
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
        self._start_container()

    def _start_container(self):
        """Démarre le conteneur Docker si ce n'est pas déjà fait."""
        client = docker.from_env()
        container_name = f"{self.model_name.replace('/', '-')}-embedder"
        try:
            # Vérifie si le conteneur existe déjà
            container = client.containers.get(container_name)
            if container.status != "running":
                container.start()
        except docker.errors.NotFound:
            # Lance un nouveau conteneur
            logger.info(f"Starting Docker container for {self.model_name}...")
            container = client.containers.run(
                image=self.docker_config["image"],
                ports={f"{self.docker_config['port']}/tcp": self.docker_config["port"]},
                detach=True,
                name=container_name,
                device_requests=[
                    docker.types.DeviceRequest(count=1, capabilities=[["gpu"]])
                ] if self.docker_config.get("gpu", False) else None,
                volumes=self.docker_config.get("volumes", []),
                environment=self.docker_config.get("environment", {}),
            )
            logger.info(f"Container {container_name} started.")
        except docker.errors.APIError as e:
            logger.error(f"Failed to start container: {e}")
            raise

        # Attend que l'API soit prête (naïf, à améliorer avec un health check)
        time.sleep(5)

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