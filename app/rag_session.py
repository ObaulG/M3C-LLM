# rag_session.py
"""
Module pour la gestion de l'historique des sessions RAG monodocument.

Ce module fournit des structures de données et un gestionnaire pour suivre
les interactions RAG (questions, réponses, sources, métriques) par session utilisateur.
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# Réutilisation du modèle RAGSource de rag_pipeline pour cohérence
# (import dynamique pour éviter les dépendances circulaires)
try:
    from rag_pipeline import RAGSource
except ImportError:
    # Définition locale de fallback
    class RAGSource(BaseModel):
        """Modèle pour une source de document RAG"""
        content: str = Field(..., description="Contenu du document")
        score_cossim: Optional[float] = Field(None, description="Score de similarité cosinus")
        score_bm25: Optional[float] = Field(None, description="Score BM25")
        metadata: Dict = Field(default_factory=dict, description="Métadonnées du document")


class RAGInteraction(BaseModel):
    """
    Représente une interaction RAG dans une session.
    
    Une interaction correspond à une question posée via le RAG monodocument,
    avec sa réponse, les sources utilisées, et les métriques de performance.
    """
    interaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question: str = Field(..., description="Question posée par l'utilisateur")
    answer: str = Field(..., description="Réponse générée par le modèle")
    sources: List[RAGSource] = Field(default_factory=list, description="Sources RAG utilisées")
    model: str = Field(..., description="Modèle utilisé pour la réponse")
    k: int = Field(..., description="Nombre de sources demandées")
    use_reranking: bool = Field(default=False, description="Reranking activé ou non")
    total_time: float = Field(..., description="Temps total de traitement en secondes")
    consumed_energy_Wh: Optional[float] = Field(None, description="Énergie consommée en Wh (modèles locaux)")
    timestamp: datetime = Field(default_factory=datetime.now, description="Horodatage de l'interaction")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Métadonnées supplémentaires (use_rag, include_quantitative, etc.)"
    )
    question_embedding: Optional[List[float]] = Field(
        default=None, 
        description="Embedding vectoriel de la question"
    )
    answer_embedding: Optional[List[float]] = Field(
        default=None, 
        description="Embedding vectoriel de la réponse"
    )


class RAGSession(BaseModel):
    """
    Représente une session RAG monodocument.
    
    Une session regroupe toutes les interactions RAG pour un document spécifique.
    """
    session_id: str = Field(..., description="Identifiant unique de la session")
    document_id: str = Field(..., description="Identifiant du document concerné")
    created_at: datetime = Field(..., description="Date de création de la session")
    updated_at: datetime = Field(..., description="Date de dernière mise à jour")
    interactions: List[RAGInteraction] = Field(
        default_factory=list, 
        description="Liste des interactions RAG de cette session"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Métadonnées de la session (user_id, tags, etc.)"
    )

    def to_messages(self, max_interactions: int = 10) -> list:
        """
        Convertit l'historique de cette session en liste de messages standard.
        Limite à max_interactions (fenêtre glissante sur les dernières interactions).
        
        Args:
            max_interactions: Nombre maximum d'interactions à inclure (défaut: 10)
        
        Returns:
            Liste de dictionnaires au format {"role": "user"|"assistant", "content": "..."}
        """
        messages = []
        # Prendre les dernières interactions (fenêtre glissante)
        interactions = self.interactions[-max_interactions:]
        for interaction in interactions:
            messages.append({"role": "user", "content": interaction.question})
            messages.append({"role": "assistant", "content": interaction.answer})
        return messages


class RAGSessionManager:
    """
    Gestionnaire des sessions RAG monodocument.
    
    Ce gestionnaire permet de créer, modifier et récupérer des sessions RAG,
    avec sauvegarde automatique dans des fichiers JSON individuels dans un dossier.
    """
    
    DEFAULT_BACKUP_DIR = "rag_sessions"
    DEFAULT_CSV_DIR = "rag_sessions_csv"

    def __init__(self, backup_dir: str = DEFAULT_BACKUP_DIR):
        """
        Initialise le gestionnaire de sessions RAG.
        
        Args:
            backup_dir: Chemin vers le dossier de sauvegarde des sessions.
                       Par défaut : 'rag_sessions'
        """
        print("Initialisation du RAGSessionManager")
        self.sessions: Dict[str, RAGSession] = {}
        self.backup_dir = backup_dir

        os.makedirs(self.backup_dir, exist_ok=True)
        #path_exists = os.path.exists(self.DEFAULT_CSV_DIR)
        #print("cwd: ", os.getcwd())
        #print(os.path.abspath(self.DEFAULT_CSV_DIR))
        #print("DEFAULT_CSV_DIR path exists:", path_exists)
        #print("trying to write ", self.DEFAULT_CSV_DIR+"/test.bin")
        #with open(self.DEFAULT_CSV_DIR+"/test.bin", "wb") as f:
        #    f.write(b"test")

        self.load_sessions()
    
    def _get_session_filepath(self, session_id: str) -> str:
        """Retourne le chemin du fichier pour une session donnée."""
        return os.path.join(self.backup_dir, f"session_{session_id}.json")
    
    def create_session(self, document_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Crée une nouvelle session RAG pour un document.
        
        Args:
            document_id: Identifiant du document concerné
            metadata: Métadonnées optionnelles pour la session
            
        Returns:
            str: L'identifiant de la session créée
        """
        session_id = str(uuid.uuid4())
        print("new session id: ", session_id)
        now = datetime.now()
        
        self.sessions[session_id] = RAGSession(
            session_id=session_id,
            document_id=document_id,
            created_at=now,
            updated_at=now,
            interactions=[],
            metadata=metadata
        )
        
        self._save_session(session_id)
        return session_id
    
    def add_interaction(
        self, 
        session_id: str, 
        interaction: RAGInteraction
    ) -> bool:
        """
        Ajoute une interaction à une session RAG.
        
        Args:
            session_id: Identifiant de la session
            interaction: L'interaction RAG à ajouter
            
        Returns:
            bool: True si l'ajout a réussi, False si la session n'existe pas
        """
        if session_id not in self.sessions:
            return False
        
        self.sessions[session_id].interactions.append(interaction)
        self.sessions[session_id].updated_at = datetime.now()
        self._save_session(session_id)
        return True
    
    def get_session(self, session_id: str) -> Optional[RAGSession]:
        """
        Récupère une session par son identifiant.
        
        Args:
            session_id: Identifiant de la session
            
        Returns:
            RAGSession ou None si non trouvée
        """
        return self.sessions.get(session_id)
    
    def get_sessions_by_document(self, document_id: str) -> List[RAGSession]:
        """
        Récupère toutes les sessions pour un document spécifique.
        
        Args:
            document_id: Identifiant du document
            
        Returns:
            Liste des sessions RAG pour ce document
        """
        return [
            session for session in self.sessions.values() 
            if session.document_id == document_id
        ]
    
    def list_sessions(self) -> List[RAGSession]:
        """
        Liste toutes les sessions RAG.
        
        Returns:
            Liste de toutes les sessions
        """
        return list(self.sessions.values())
    
    def delete_session(self, session_id: str) -> bool:
        """
        Supprime une session.
        
        Args:
            session_id: Identifiant de la session à supprimer
            
        Returns:
            bool: True si la suppression a réussi, False sinon
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            # Supprimer le fichier
            filepath = self._get_session_filepath(session_id)
            if os.path.exists(filepath):
                os.remove(filepath)
            return True
        return False
    
    def export_session_to_json(self, session_id: str) -> Optional[str]:
        """
        Exporte une session au format JSON.
        
        Args:
            session_id: Identifiant de la session
            
        Returns:
            Chaîne JSON ou None si session non trouvée
        """
        session = self.get_session(session_id)
        if session:
            return session.model_dump_json(indent=2, ensure_ascii=False, exclude_none=True)
        return None
    
    def export_session_to_csv(self, session_id: str) -> bool:
        """
        Exporte une session au format CSV.
        
        Args:
            session_id: Identifiant de la session
            file_path: Chemin du fichier CSV de destination
            
        Returns:
            bool: True si l'export a réussi, False sinon
        """
        import csv
        
        session = self.get_session(session_id)
        if not session:
            return False

        print(session)
        with open(self.DEFAULT_CSV_DIR+"/"+session_id+".csv",
                  'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'interaction_id',
                'timestamp', 
                'question',
                'answer',
                'model',
                'k',
                'use_reranking',
                'total_time',
                'consumed_energy_Wh',
                'num_sources',
                'document_id'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            
            for interaction in session.interactions:
                row = {
                    'interaction_id': interaction.interaction_id,
                    'timestamp': interaction.timestamp.isoformat(),
                    'question': interaction.question,
                    'answer': interaction.answer,
                    'model': interaction.model,
                    'k': interaction.k,
                    'use_reranking': interaction.use_reranking,
                    'total_time': interaction.total_time,
                    'consumed_energy_Wh': interaction.consumed_energy_Wh,
                    'num_sources': len(interaction.sources),
                    'document_id': session.document_id
                }
                writer.writerow(row)
        
        return True
    
    def _save_session(self, session_id: str):
        """
        Sauvegarde une session spécifique dans son fichier.
        
        Args:
            session_id: Identifiant de la session à sauvegarder
        """
        if session_id not in self.sessions:
            return
            
        try:
            filepath = self._get_session_filepath(session_id)
            session = self.sessions[session_id]
            session_data = session.model_dump(exclude_none=True)
            # Convertir les datetime en chaînes ISO pour la sérialisation JSON
            if 'created_at' in session_data and isinstance(session_data['created_at'], datetime):
                session_data['created_at'] = session_data['created_at'].isoformat()
            if 'updated_at' in session_data and isinstance(session_data['updated_at'], datetime):
                session_data['updated_at'] = session_data['updated_at'].isoformat()
            if 'interactions' in session_data:
                for interaction in session_data['interactions']:
                    if 'timestamp' in interaction and isinstance(interaction['timestamp'], datetime):
                        interaction['timestamp'] = interaction['timestamp'].isoformat()

                    # for each interaction in "interactions", for each source in "sources", in "metadata, in "document_data",
                    # convert "created_at" and "updated_at"
                    for source in interaction['sources']:
                        print(source["metadata"])
                        source["metadata"]["document_data"]["created_at"] = source["metadata"]["document_data"]["created_at"].isoformat()
                        source["metadata"]["document_data"]["updated_at"] = source["metadata"]["document_data"]["updated_at"].isoformat()
            print("Sauvegarde dans fichier")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erreur lors de la sauvegarde de la session {session_id}: {e}")
    
    def _save_all_sessions(self):
        """Sauvegarde toutes les sessions (pour compatibilité)."""
        for session_id in self.sessions:
            self._save_session(session_id)
    
    def _load_session_from_file(self, filepath: str):
        """Charge une session depuis un fichier JSON."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
                
                # Conversion des chaînes de date en datetime
                if isinstance(session_data.get('created_at'), str):
                    session_data['created_at'] = datetime.fromisoformat(session_data['created_at'])
                if isinstance(session_data.get('updated_at'), str):
                    session_data['updated_at'] = datetime.fromisoformat(session_data['updated_at'])
                
                # Conversion des interactions
                if 'interactions' in session_data:
                    for interaction in session_data['interactions']:
                        if isinstance(interaction.get('timestamp'), str):
                            interaction['timestamp'] = datetime.fromisoformat(interaction['timestamp'])
                
                session = RAGSession(**session_data)
                self.sessions[session.session_id] = session
        except Exception as e:
            print(f"Erreur lors du chargement du fichier {filepath}: {e}")
    
    def load_sessions(self):
        """
        Charge toutes les sessions depuis les fichiers du dossier de backup.
        """
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir, exist_ok=True)
            self.sessions = {}
            return
        
        # Charger tous les fichiers JSON du dossier
        for filename in os.listdir(self.backup_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.backup_dir, filename)
                self._load_session_from_file(filepath)

    def convert_session_dict_to_messages(self, session_dict: dict, max_interactions: int = 10) -> list:
        """
        Convertit un dict de session (issu de export_session_to_json) en liste de messages standard.
        
        Args:
            session_dict: Dictionnaire représentant une session RAG
            max_interactions: Nombre maximum d'interactions à inclure (défaut: 10)
        
        Returns:
            Liste de dictionnaires au format {"role": "user"|"assistant", "content": "..."}
        """
        messages = []
        interactions = session_dict.get('interactions', [])[-max_interactions:]
        for interaction in interactions:
            messages.append({"role": "user", "content": interaction.get('question', '')})
            messages.append({"role": "assistant", "content": interaction.get('answer', '')})
        return messages