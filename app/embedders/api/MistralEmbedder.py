# embedders/api/mistral.py
from app.embedders.BaseEmbedder import BaseEmbedder
from typing import List
import os
from mistralai.client import Mistral

# Note: il n'est pas possible de donner une dimension lors d'un appel embeddings.create...

class MistralEmbedder(BaseEmbedder):
    def __init__(self, api_key: str, model: str = "mistral-embed", dimension: int = 1024) -> None:
        self.model = model
        self.dimension = dimension
        self._api_key = api_key or os.getenv("MISTRAL_API_KEY", "")

    @property
    def name(self) -> str:
        return f"mistral-{self.model}"

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