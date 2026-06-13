# embedders/api/mistral.py
from embedders import BaseEmbedder
from typing import List
import requests
import os
from mistralai.client import Mistral

class MistralEmbedder(BaseEmbedder):
    def __init__(self, api_key: str, model: str = "mistral-embed", dimension: int = 1024) -> None:
        self.model = model
        self.dimension = dimension

    def embed(self, text: str) -> List[float]:
        with Mistral(api_key=os.getenv("MISTRAL_API_KEY", "")) as mistral:
            res = mistral.embeddings.create(model=self.model, input=text, output_dimension = self.dimension),
        return res

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        with Mistral(api_key=os.getenv("MISTRAL_API_KEY", "")) as mistral:
            res = mistral.embeddings.create(model=self.model, inputs=texts, output_dimension=self.dimension),
        return res

    def dimension(self) -> int:
        return self.dimension  # Dimension pour mistral-embed