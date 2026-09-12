from abc import ABC, abstractmethod
from typing import List, Union

class BaseEmbedder(ABC):
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Embed un seul texte."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed une liste de textes."""
        pass

    @abstractmethod
    def dimension(self) -> int:
        """Retourne la dimension des embeddings (ex: 384 pour `all-MiniLM-L6-v2`)."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Nom de l'embedder (ex: 'OpenAI')."""
        pass

    @abstractmethod
    def ping(self) -> bool:
        """Vérifie que l'embedder est disponible (ex: API reachable, modèle chargé)."""
        pass

    def embed_query(self, text: str) -> List[float]:
        """Embed un texte (alias pour compatibilité avec l'ancien code)."""
        return self.embed(text)