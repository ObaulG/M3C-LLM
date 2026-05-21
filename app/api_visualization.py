"""
API routes for RAG visualization with t-SNE projection.
Provides endpoints to retrieve embeddings and compute 2D projections.
Also provides endpoints for query embedding comparison.
"""
import json
import os
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from database.database import get_db_connection, get_all_documents, get_chunks_for_document, get_chunk_embeddings_with_metadata
from rag_session import RAGSessionManager

import numpy as np
from openTSNE import TSNE

# Global variable to store the rag_pipeline for embedding generation
# Will be set from api_server after initialization
RAG_PIPELINE = None


def set_rag_pipeline(pipeline):
    """Set the RAG pipeline reference for embedding generation."""
    global RAG_PIPELINE
    RAG_PIPELINE = pipeline


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calcule la similarité cosinus entre deux vecteurs."""
    a_arr = np.array(a, dtype=np.float32)
    b_arr = np.array(b, dtype=np.float32)
    dot_product = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot_product / (norm_a * norm_b))


def compute_similarity_matrix(embeddings: List[List[float]]) -> List[List[float]]:
    """Calcule la matrice de similarité entre tous les embeddings."""
    n = len(embeddings)
    matrix = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(cosine_similarity(embeddings[i], embeddings[j]))
        matrix.append(row)
    return matrix


async def generate_embedding(text: str) -> List[float]:
    """Génère l'embedding d'un texte en utilisant le pipeline RAG."""
    global RAG_PIPELINE
    
    if RAG_PIPELINE is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG pipeline not initialized. Cannot generate embeddings."
        )
    
    try:
        if hasattr(RAG_PIPELINE, '_get_prompt_embeddings'):
            return RAG_PIPELINE._get_prompt_embeddings(text)
        elif hasattr(RAG_PIPELINE, 'embedder'):
            return RAG_PIPELINE.embedder.embed_query(text)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="RAG pipeline does not have an embedding method"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating embedding: {str(e)}"
        )


router = APIRouter(tags=["RAG Visualization"])

# ============================================================================
# MODELS
# ============================================================================

class EmbeddingData(BaseModel):
    """Embedding data for a chunk or query."""
    chunk_id: str = Field(..., description="Unique identifier for the chunk")
    document_id: str = Field(..., description="Document identifier")
    content: Optional[str] = Field(..., description="Text content of the chunk")
    embedding: List[float] = Field(..., description="Embedding vector")
    num_page: Optional[int] = Field(None, description="Page number in the document")
    position_in_page: Optional[int] = Field(None, description="Position within the page")
    token_count: Optional[int] = Field(None, description="Number of tokens in the chunk")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class EmbeddingsResponse(BaseModel):
    """Response containing embeddings data."""
    chunks: List[EmbeddingData] = Field(default_factory=list, description="List of chunk embeddings")
    queries: List[Dict[str, Any]] = Field(default_factory=list, description="List of query embeddings")
    document_id: Optional[str] = Field(None, description="Filter by document ID")
    model_name: str = Field(..., description="Name of the embedding model used")
    count: int = Field(..., description="Total number of embeddings returned")
    timestamp: str = Field(..., description="Response timestamp")


class TSNERequest(BaseModel):
    """Request to compute t-SNE projection."""
    embeddings: List[List[float]] = Field(..., description="List of embedding vectors to project")
    n_components: int = Field(2, description="Number of dimensions to project to", ge=1, le=3)
    perplexity: float = Field(30.0, description="t-SNE perplexity parameter", ge=5.0, le=50.0)
    learning_rate: float = Field(200.0, description="t-SNE learning rate", ge=10.0, le=1000.0)
    n_iter: int = Field(1000, description="Number of iterations", ge=250, le=5000)
    random_state: Optional[int] = Field(None, description="Random seed for reproducibility")


class TSNEResponse(BaseModel):
    """Response containing t-SNE projection results."""
    projected_embeddings: List[List[float]] = Field(..., description="2D/3D projected coordinates")
    parameters: Dict[str, Any] = Field(..., description="Parameters used for the projection")
    timestamp: str = Field(..., description="Response timestamp")


class QueryEmbedding(BaseModel):
    """Query with its embedding."""
    query_id: str = Field(..., description="Unique query identifier")
    text: str = Field(..., description="Query text")
    embedding: List[float] = Field(..., description="Query embedding vector")
    timestamp: str = Field(..., description="When the query was made")
    model: str = Field(..., description="Model used for the query")


class InteractionWithEmbeddings(BaseModel):
    """RAG interaction with embedding data."""
    interaction_id: str
    question: str
    answer: str
    question_embedding: Optional[List[float]] = None
    answer_embedding: Optional[List[float]] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    model: str
    k: int
    use_reranking: bool
    total_time: float
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None


# New models for query comparison endpoints

class QueryEmbeddingRequest(BaseModel):
    """Request to generate an embedding for a query."""
    query: str = Field(..., description="Query text to embed")
    document_id: Optional[str] = Field(None, description="Optional document ID for context")
    session_id: Optional[str] = Field(None, description="Optional session ID for context")


class QueryEmbeddingResponse(BaseModel):
    """Response with a query embedding."""
    query_id: str = Field(..., description="Unique identifier for this query embedding")
    query: str = Field(..., description="Original query text")
    embedding: List[float] = Field(..., description="Generated embedding vector")
    timestamp: str = Field(..., description="When the embedding was generated")
    model: str = Field(..., description="Embedding model used")


class ChunkSimilarity(BaseModel):
    """Similarity result between a query and a document chunk."""
    chunk_id: str = Field(..., description="Identifier of the chunk")
    similarity: float = Field(..., description="Cosine similarity score (0-1)")
    content: str = Field(..., description="Text content of the chunk")
    num_page: Optional[int] = Field(None, description="Page number")
    position_in_page: Optional[int] = Field(None, description="Position within page")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class QueryDocumentComparisonRequest(BaseModel):
    """Request to compare a query with document chunks."""
    query: str = Field(..., description="Query text to compare")
    document_id: str = Field(..., description="Document ID to compare against")
    k: int = Field(5, description="Number of top similar chunks to return", ge=1, le=50)


class QueryDocumentComparisonResponse(BaseModel):
    """Response with query-document similarity results."""
    query_embedding: List[float] = Field(..., description="Embedding of the query")
    query_id: str = Field(..., description="Unique query identifier")
    document_id: str = Field(..., description="Document ID compared")
    chunk_similarities: List[ChunkSimilarity] = Field(
        default_factory=list, 
        description="Similarity scores for all chunks"
    )
    top_matches: List[ChunkSimilarity] = Field(
        default_factory=list,
        description="Top k most similar chunks"
    )


class MultipleQueriesComparisonRequest(BaseModel):
    """Request to compare multiple queries."""
    queries: List[str] = Field(..., description="List of query texts", min_length=1)
    session_id: Optional[str] = Field(None, description="Optional session ID for context")
    document_id: Optional[str] = Field(None, description="Optional document ID to compare against")


class MultipleQueriesComparisonResponse(BaseModel):
    """Response with multiple query comparison results."""
    query_embeddings: List[List[float]] = Field(..., description="Embeddings for all queries")
    query_texts: List[str] = Field(..., description="Original query texts")
    query_ids: List[str] = Field(..., description="Unique identifiers for each query")
    similarity_matrix: List[List[float]] = Field(..., description="Pairwise similarity matrix")
    document_similarities: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Similarities with document chunks (if document_id provided)"
    )


class SessionQueriesResponse(BaseModel):
    """Response with all queries from a session."""
    session_id: str = Field(..., description="Session identifier")
    document_id: str = Field(..., description="Document ID for this session")
    queries: List[QueryEmbeddingResponse] = Field(
        default_factory=list,
        description="List of queries with their embeddings"
    )


class VisualizationDataResponse(BaseModel):
    """Complete visualization data including documents and queries."""
    document_id: str = Field(..., description="Document identifier")
    document_embeddings: List[EmbeddingData] = Field(
        default_factory=list,
        description="Embeddings of document chunks"
    )
    query_embeddings: List[QueryEmbeddingResponse] = Field(
        default_factory=list,
        description="Embeddings of queries"
    )
    projected_coordinates: Dict[str, List[List[float]]] = Field(
        default_factory=dict,
        description="2D/3D coordinates for visualization"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters used for projection"
    )
    timestamp: str = Field(..., description="Response timestamp")


# ============================================================================
# INITIALIZATION
# ============================================================================

# Initialize session manager
rag_session_manager = RAGSessionManager()

# Get the embedding model name from the pipeline (will be set after RAG initialization)
EMBEDDING_MODEL_NAME = "mistral-embed"


def set_embedding_model(model_name: str):
    """Set the embedding model name (called from api_server after RAG init)."""
    global EMBEDDING_MODEL_NAME
    EMBEDDING_MODEL_NAME = model_name


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/embeddings", response_model=EmbeddingsResponse, tags=["Embeddings"])
async def get_embeddings(
    document_id: Optional[str] = None,
    limit: Optional[int] = None,
    model_name: Optional[str] = None
):
    """
    Retrieve chunk embeddings from the database.
    
    Args:
        document_id: Optional filter by document ID
        limit: Maximum number of embeddings to return
        model_name: Embedding model name (defaults to the pipeline's model)
    
    Returns:
        EmbeddingsResponse with chunk embeddings and optional query embeddings
    """
    if model_name is None:
        model_name = EMBEDDING_MODEL_NAME
    
    try:
        conn = await get_db_connection()
        
        chunks_data = await get_chunk_embeddings_with_metadata(
            conn, document_id, limit, False, model_name
        )
        
        await conn.close()
        print(f"{len(chunks_data)} embeddings retrieved")
        
        chunks = []
        for row in chunks_data:
            chunks.append(EmbeddingData(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                content="",
                embedding=json.loads(row["embedding"]),
                num_page=row["num_page"],
                position_in_page=row["position_in_page"],
                token_count=row["token_count"],
                metadata=row["metadata"]
            ))
        
        queries = []
        
        return EmbeddingsResponse(
            chunks=chunks,
            queries=queries,
            document_id=document_id,
            model_name=model_name,
            count=len(chunks),
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving embeddings: {str(e)}"
        )


@router.post("/visualization/tsne", response_model=TSNEResponse, tags=["Visualization"])
async def compute_tsne_projection(request: TSNERequest):
    """
    Compute t-SNE projection for a set of embeddings.
    
    Uses the openTSNE library to reduce dimensionality to 2D (or 3D).
    
    Args:
        request: TSNERequest containing embeddings and parameters
    
    Returns:
        TSNEResponse with 2D/3D projected coordinates
    """
    try:
        embeddings_array = np.array(request.embeddings, dtype=np.float32)
        print("embeddings converted to np.array")
        
        if embeddings_array.size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No embeddings provided"
            )
        
        if embeddings_array.ndim != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Embeddings must be a 2D array (samples x features)"
            )
        
        tsne = TSNE(
            n_components=request.n_components,
            perplexity=request.perplexity,
            learning_rate=request.learning_rate,
            n_iter=request.n_iter,
            random_state=request.random_state,
            verbose=False
        )
        print("tsne created")
        
        projected = tsne.fit(embeddings_array)
        print("tsne projected")
        
        projected_embeddings = projected.tolist()
        print("tsne projected embeddings")
        
        return TSNEResponse(
            projected_embeddings=projected_embeddings,
            parameters={
                "n_components": request.n_components,
                "perplexity": request.perplexity,
                "learning_rate": request.learning_rate,
                "n_iter": request.n_iter,
                "input_shape": embeddings_array.shape,
                "random_state": request.random_state
            },
            timestamp=datetime.now().isoformat()
        )
        
    except ImportError as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"openTSNE library not installed: {str(e)}. Please install with: pip install opentsne scikit-learn"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error computing t-SNE: {str(e)}"
        )


@router.get("/sessions/{session_id}/interactions", tags=["Sessions"])
async def get_session_interactions_with_embeddings(session_id: str):
    """
    Retrieve RAG session interactions with embedding data.
    
    For each interaction, if embeddings are available in the session data,
    they will be included in the response.
    
    Args:
        session_id: The session identifier
    
    Returns:
        List of interactions with optional embedding data
    """
    try:
        session = rag_session_manager.get_session(session_id)
        
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        interactions = []
        for interaction in session.interactions:
            question_embedding = None
            answer_embedding = None
            
            if interaction.metadata:
                question_embedding = interaction.metadata.get("question_embedding")
                answer_embedding = interaction.metadata.get("answer_embedding")
            
            sources_list = []
            for source in interaction.sources:
                sources_list.append({
                    "content": source.content,
                    "score_cossim": source.score_cossim,
                    "score_bm25": source.score_bm25,
                    "metadata": source.metadata,
                    "embedding": source.metadata.get("embedding") if source.metadata else None
                })
            
            interactions.append(InteractionWithEmbeddings(
                interaction_id=interaction.interaction_id,
                question=interaction.question,
                answer=interaction.answer,
                question_embedding=question_embedding,
                answer_embedding=answer_embedding,
                sources=sources_list,
                model=interaction.model,
                k=interaction.k,
                use_reranking=interaction.use_reranking,
                total_time=interaction.total_time,
                timestamp=interaction.timestamp.isoformat(),
                metadata=interaction.metadata
            ))
        
        return {
            "session_id": session_id,
            "document_id": session.document_id,
            "interactions": interactions
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving session interactions: {str(e)}"
        )


# ============================================================================
# NEW ENDPOINTS FOR QUERY EMBEDDING COMPARISON
# ============================================================================


@router.post("/query-embedding", response_model=QueryEmbeddingResponse, tags=["Query Comparison"])
async def create_query_embedding(request: QueryEmbeddingRequest):
    """
    Generate an embedding for a query text.
    
    This endpoint creates a vector embedding for a user query, which can then be
    compared with document embeddings or other query embeddings.
    
    Args:
        request: QueryEmbeddingRequest containing the query text
        
    Returns:
        QueryEmbeddingResponse with the generated embedding
    """
    try:
        query_id = str(uuid.uuid4())
        embedding = await generate_embedding(request.query)
        model_name = EMBEDDING_MODEL_NAME
        if RAG_PIPELINE and hasattr(RAG_PIPELINE, 'embedder_name'):
            model_name = RAG_PIPELINE.embedder_name
        return QueryEmbeddingResponse(
            query_id=query_id,
            query=request.query,
            embedding=embedding,
            timestamp=datetime.now().isoformat(),
            model=model_name
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating query embedding: {str(e)}"
        )


@router.post("/compare-query-document", response_model=QueryDocumentComparisonResponse, tags=["Query Comparison"])
async def compare_query_with_document(request: QueryDocumentComparisonRequest):
    """
    Compare a query embedding with all chunks from a document.
    
    Generates the query embedding and compares it with all embeddings from
    the specified document, returning similarity scores for each chunk.
    
    Args:
        request: QueryDocumentComparisonRequest with query and document_id
        
    Returns:
        QueryDocumentComparisonResponse with similarity scores and top matches
    """
    try:
        query_id = str(uuid.uuid4())
        query_embedding = await generate_embedding(request.query)
        
        conn = await get_db_connection()
        chunks_data = await get_chunk_embeddings_with_metadata(
            conn, request.document_id, None, False, EMBEDDING_MODEL_NAME
        )
        await conn.close()
        
        if not chunks_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No chunks found for document {request.document_id}"
            )
        
        chunk_similarities = []
        for row in chunks_data:
            chunk_embedding = json.loads(row["embedding"])
            similarity = cosine_similarity(query_embedding, chunk_embedding)
            
            chunk_similarities.append(ChunkSimilarity(
                chunk_id=row["chunk_id"],
                similarity=round(similarity, 6),
                content=row["content"][:500] + "..." if len(row["content"]) > 500 else row["content"],
                num_page=row["num_page"],
                position_in_page=row["position_in_page"],
                metadata=row["metadata"]
            ))
        
        sorted_similarities = sorted(chunk_similarities, key=lambda x: x.similarity, reverse=True)
        top_matches = sorted_similarities[:request.k]
        
        return QueryDocumentComparisonResponse(
            query_embedding=query_embedding,
            query_id=query_id,
            document_id=request.document_id,
            chunk_similarities=chunk_similarities,
            top_matches=top_matches
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error comparing query with document: {str(e)}"
        )


@router.get("/sessions/{session_id}/queries", response_model=SessionQueriesResponse, tags=["Query Comparison"])
async def get_session_queries(session_id: str):
    """
    Retrieve all queries with embeddings from a RAG session.
    
    Returns all the queries posed during a session, along with their embeddings
    for visualization and comparison purposes.
    
    Args:
        session_id: The RAG session identifier
        
    Returns:
        SessionQueriesResponse with all queries and their embeddings
    """
    try:
        session = rag_session_manager.get_session(session_id)
        
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        queries = []
        for interaction in session.interactions:
            if interaction.question_embedding:
                queries.append(QueryEmbeddingResponse(
                    query_id=interaction.interaction_id,
                    query=interaction.question,
                    embedding=interaction.question_embedding,
                    timestamp=interaction.timestamp.isoformat(),
                    model=interaction.model
                ))
        
        return SessionQueriesResponse(
            session_id=session_id,
            document_id=session.document_id,
            queries=queries
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving session queries: {str(e)}"
        )


@router.post("/compare-multiple-queries", response_model=MultipleQueriesComparisonResponse, tags=["Query Comparison"])
async def compare_multiple_queries(request: MultipleQueriesComparisonRequest):
    """
    Compare multiple queries by calculating their pairwise similarities.
    
    Generates embeddings for all queries and computes a similarity matrix
    showing how similar each query is to every other query.
    
    Args:
        request: MultipleQueriesComparisonRequest with list of queries
        
    Returns:
        MultipleQueriesComparisonResponse with similarity matrix
    """
    try:
        if not request.queries:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one query must be provided"
            )
        
        query_embeddings = []
        query_ids = []
        query_texts = []
        
        for query in request.queries:
            query_id = str(uuid.uuid4())
            embedding = await generate_embedding(query)
            query_embeddings.append(embedding)
            query_ids.append(query_id)
            query_texts.append(query)
        
        similarity_matrix = compute_similarity_matrix(query_embeddings)
        
        document_similarities = None
        if request.document_id:
            conn = await get_db_connection()
            chunks_data = await get_chunk_embeddings_with_metadata(
                conn, request.document_id, None, False, EMBEDDING_MODEL_NAME
            )
            await conn.close()
            
            if chunks_data:
                document_similarities = []
                for i, q_embedding in enumerate(query_embeddings):
                    chunk_sims = []
                    for row in chunks_data:
                        chunk_embedding = json.loads(row["embedding"])
                        sim = cosine_similarity(q_embedding, chunk_embedding)
                        chunk_sims.append(sim)
                    avg_sim = sum(chunk_sims) / len(chunk_sims) if chunk_sims else 0.0
                    document_similarities.append({
                        "query_id": query_ids[i],
                        "query_index": i,
                        "average_similarity": avg_sim,
                        "document_id": request.document_id
                    })
        
        return MultipleQueriesComparisonResponse(
            query_embeddings=query_embeddings,
            query_texts=query_texts,
            query_ids=query_ids,
            similarity_matrix=similarity_matrix,
            document_similarities=document_similarities
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error comparing multiple queries: {str(e)}"
        )


@router.get("/visualization-data/{document_id}", response_model=VisualizationDataResponse, tags=["Visualization"])
async def get_visualization_data(
    document_id: str,
    session_id: Optional[str] = None
):
    """
    Retrieve complete visualization data for a document and optional session queries.
    
    Returns document chunk embeddings and query embeddings (if session provided)
    ready for t-SNE projection and visualization.
    
    Args:
        document_id: The document identifier
        session_id: Optional RAG session ID to include query embeddings
        
    Returns:
        VisualizationDataResponse with all data needed for visualization
    """
    try:
        conn = await get_db_connection()
        chunks_data = await get_chunk_embeddings_with_metadata(
            conn, document_id, None, False, EMBEDDING_MODEL_NAME
        )
        await conn.close()
        
        document_embeddings = []
        for row in chunks_data:
            document_embeddings.append(EmbeddingData(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                content=row["content"],
                embedding=json.loads(row["embedding"]),
                num_page=row["num_page"],
                position_in_page=row["position_in_page"],
                token_count=row["token_count"],
                metadata=row["metadata"]
            ))
        
        query_embeddings = []
        if session_id:
            session = rag_session_manager.get_session(session_id)
            if session:
                for interaction in session.interactions:
                    if interaction.question_embedding:
                        query_embeddings.append(QueryEmbeddingResponse(
                            query_id=interaction.interaction_id,
                            query=interaction.question,
                            embedding=interaction.question_embedding,
                            timestamp=interaction.timestamp.isoformat(),
                            model=interaction.model
                        ))
        
        all_embeddings = [d.embedding for d in document_embeddings] + \
                         [q.embedding for q in query_embeddings]
        
        projected_coordinates = {"document_points": [], "query_points": []}
        parameters = {}
        
        if all_embeddings and len(all_embeddings) > 1:
            tsne_request = TSNERequest(
                embeddings=all_embeddings,
                n_components=2,
                perplexity=30.0,
                learning_rate=200.0,
                n_iter=1000
            )
            tsne_response = await compute_tsne_projection(tsne_request)
            
            num_docs = len(document_embeddings)
            projected_coordinates["document_points"] = tsne_response.projected_embeddings[:num_docs]
            projected_coordinates["query_points"] = tsne_response.projected_embeddings[num_docs:]
            parameters = tsne_response.parameters
        
        return VisualizationDataResponse(
            document_id=document_id,
            document_embeddings=document_embeddings,
            query_embeddings=query_embeddings,
            projected_coordinates=projected_coordinates,
            parameters=parameters,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving visualization data: {str(e)}"
        )
