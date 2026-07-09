"""
Gestionnaire Server-Sent Events pour les jobs d'indexation Solr.
"""
import asyncio
from typing import Dict, Any
from collections import defaultdict


class SolrSSEManager:
    """
    Gestionnaire de connexions SSE pour les jobs Solr.
    """
    
    def __init__(self):
        self.connections: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self.lock = asyncio.Lock()
    
    async def connect(self, job_id: str) -> asyncio.Queue:
        """
        Crée une nouvelle connexion pour un job.
        
        Args:
            job_id: ID du job à écouter
        
        Returns:
            File d'attente pour recevoir les événements
        """
        async with self.lock:
            if job_id not in self.connections:
                self.connections[job_id] = asyncio.Queue()
            return self.connections[job_id]
    
    async def disconnect(self, job_id: str, queue: asyncio.Queue):
        """
        Ferme une connexion SSE.
        
        Args:
            job_id: ID du job
            queue: File d'attente à fermer
        """
        async with self.lock:
            if job_id in self.connections and self.connections[job_id] == queue:
                del self.connections[job_id]
    
    async def send_event(self, job_id: str, event_type: str, data: Dict[str, Any]):
        """
        Envoie un événement à tous les clients connectés à un job.
        
        Args:
            job_id: ID du job
            event_type: Type d'événement (ex: 'progress', 'completed', 'failed')
            data: Données de l'événement
        """
        async with self.lock:
            if job_id in self.connections:
                queue = self.connections[job_id]
                await queue.put({
                    "event": event_type,
                    "data": data,
                    "timestamp": asyncio.get_event_loop().time()
                })
    
    async def broadcast_all(self, event_type: str, data: Dict[str, Any]):
        """
        Envoie un événement à tous les jobs.
        
        Args:
            event_type: Type d'événement
            data: Données de l'événement
        """
        async with self.lock:
            for job_id, queue in self.connections.items():
                await queue.put({
                    "event": event_type,
                    "data": data,
                    "timestamp": asyncio.get_event_loop().time()
                })


# Instance globale du gestionnaire
sse_manager = SolrSSEManager()
