from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime

class Document(BaseModel):
    document_id: str
    file_name: str
    file_path: str
    file_size: int
    created_at: datetime
    updated_at: datetime

class ChunkingStrategy(BaseModel):
    strategy_id: int
    name: str
    description: Optional[str]

class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    strategy_id: int
    content: str
    num_page: int
    token_count: int
    metadata: Dict
    created_at: datetime

class ChunkWithEmbedding(Chunk):
    embedding: List[float]
