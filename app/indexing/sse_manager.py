"""Gestionnaire des connexions Server-Sent Events pour les jobs d'indexation."""
import asyncio
from typing import Dict, Set


class SSEManager:
    """Gère les connexions SSE pour les notifications de jobs d'indexation."""
    
    def __init__(self):
        self.connections: Dict[str, Set[asyncio.Queue]] = {}
        self.lock = asyncio.Lock()
    
    async def connect(self, job_id: str) -> asyncio.Queue:
        """
        Ajoute une nouvelle connexion pour un job_id.
        
        Args:
            job_id: Identifiant du job
            
        Returns:
            Une queue asynchrone pour recevoir les événements
        """
        async with self.lock:
            if job_id not in self.connections:
                self.connections[job_id] = set()
            queue = asyncio.Queue()
            self.connections[job_id].add(queue)
            return queue
    
    async def disconnect(self, job_id: str, queue: asyncio.Queue):
        """
        Retire une connexion.
        
        Args:
            job_id: Identifiant du job
            queue: La queue à retirer
        """
        async with self.lock:
            if job_id in self.connections:
                self.connections[job_id].discard(queue)
                if not self.connections[job_id]:
                    del self.connections[job_id]
    
    async def send_event(self, job_id: str, event_type: str, data: dict):
        """
        Envoyer un événement à tous les clients abonnés à ce job.
        
        Args:
            job_id: Identifiant du job
            event_type: Type de l'événement (ex: 'job_completed')
            data: Données à envoyer avec l'événement
        """
        async with self.lock:
            if job_id in self.connections:
                for queue in self.connections[job_id]:
                    await queue.put({"event": event_type, "data": data})


# Instance globale du gestionnaire
sse_manager = SSEManager()
