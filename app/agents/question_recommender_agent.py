"""
Agent pour recommander les questions les plus pertinentes d'un document.

Cet agent récupère toutes les questions d'un document et les classe par pertinence
par rapport à un prompt utilisateur en utilisant les embeddings du RAG pipeline.
"""
from typing import List, Optional
import numpy as np

from ..database.database import get_questions_by_document_id, get_db_connection


class QuestionRecommendationInput:
    """Entrée pour la recommandation de questions."""
    def __init__(self, user_prompt: str, document_id: str, k: int = 5):
        self.user_prompt = user_prompt
        self.document_id = document_id
        self.k = k


class RecommendedQuestion:
    """Une question recommandée avec son score de pertinence."""
    def __init__(
        self,
        question_id: str,
        question_text: str,
        answers: List[str],
        relevance_score: float,
        chunk_id: Optional[str] = None,
        num_page: Optional[int] = None
    ):
        self.question_id = question_id
        self.question_text = question_text
        self.answers = answers
        self.relevance_score = relevance_score
        self.chunk_id = chunk_id
        self.num_page = num_page
    
    def to_dict(self) -> dict:
        """Convertit en dictionnaire pour la compatibilité."""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "answers": self.answers,
            "relevance_score": self.relevance_score,
            "chunk_id": self.chunk_id,
            "num_page": self.num_page
        }


class RecommendedQuestionsList:
    """Liste des questions recommandées."""
    def __init__(self, questions: List[RecommendedQuestion]):
        self.questions = questions
    
    def to_dict_list(self) -> List[dict]:
        """Convertit en liste de dictionnaires."""
        return [q.to_dict() for q in self.questions]


class QuestionRecommenderAgent:
    """
    Agent qui recommande les questions les plus pertinentes d'un document
    par rapport à un prompt utilisateur, en utilisant les embeddings du RAG pipeline.
    
    Cet agent n'utilise pas de LLM, uniquement les capacités d'embedding du pipeline RAG
    pour calculer les similarités entre le prompt et les questions.
    """
    
    def __init__(self, rag_pipeline):
        """
        Initialise l'agent avec une instance RAGPipeline existante.
        
        Args:
            rag_pipeline: Instance de RAGPipeline partagée. Doit avoir une méthode
                        _get_prompt_embeddings(prompt) -> List[float]
        """
        self.rag_pipeline = rag_pipeline
    
    async def run(self, input_data: QuestionRecommendationInput) -> RecommendedQuestionsList:
        """
        Exécute la recommandation de questions.
        
        Args:
            input_data: Contient user_prompt, document_id et k
            
        Returns:
            RecommendedQuestionsList avec les questions les plus pertinentes
        """
        # 1. Récupérer toutes les questions du document
        conn = await get_db_connection()
        all_questions = await get_questions_by_document_id(
            document_id=input_data.document_id,
            conn=conn,
            include_answers=True
        )
        await conn.close()
        
        if not all_questions:
            return RecommendedQuestionsList(questions=[])
        
        # 2. Embedder le prompt utilisateur
        try:
            prompt_embedding = self.rag_pipeline._get_prompt_embeddings(input_data.user_prompt)
        except Exception as e:
            print(f"Erreur lors de l'embedding du prompt: {e}")
            return RecommendedQuestionsList(questions=[])
        
        # 3. Embedder chaque question et calculer la similarité
        scored_questions = []
        for q in all_questions:
            question_text = q.get("content", "")
            if not question_text:
                continue
                
            try:
                # Embedder la question
                question_embedding = self.rag_pipeline._get_prompt_embeddings(question_text)
                
                # Calculer la similarité cosinus
                score = self._cosine_similarity(prompt_embedding, question_embedding)
                
                scored_questions.append({
                    "question": q,
                    "score": score
                })
            except Exception as e:
                print(f"Erreur lors du traitement de la question {q.get('question_id')}: {e}")
                continue
        
        # 4. Trier par score décroissant et prendre les top k
        scored_questions.sort(key=lambda x: x["score"], reverse=True)
        top_questions = scored_questions[:input_data.k]
        
        # 5. Formater le résultat
        recommended = []
        for item in top_questions:
            q = item["question"]
            answers = [a["content"] for a in q.get("answers", [])]
            recommended.append(RecommendedQuestion(
                question_id=str(q.get("question_id", "")),
                question_text=q.get("content", ""),
                answers=answers,
                relevance_score=float(item["score"]),
                chunk_id=str(q.get("chunk_id")) if q.get("chunk_id") else None,
                num_page=q.get("num_page")
            ))
        
        return RecommendedQuestionsList(questions=recommended)
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calcule la similarité cosinus entre deux vecteurs.
        
        Args:
            vec1: Premier vecteur d'embeddings
            vec2: Deuxième vecteur d'embeddings
            
        Returns:
            Score de similarité entre 0 et 1 (1 = parfaitement similaire)
        """
        try:
            vec1_arr = np.array(vec1, dtype=np.float32)
            vec2_arr = np.array(vec2, dtype=np.float32)
            
            # Normaliser les vecteurs
            vec1_norm = vec1_arr / (np.linalg.norm(vec1_arr) + 1e-8)
            vec2_norm = vec2_arr / (np.linalg.norm(vec2_arr) + 1e-8)
            
            # Produit scalaire des vecteurs normalisés
            similarity = float(np.dot(vec1_norm, vec2_norm))
            
            # Assurer que le résultat est dans [0, 1]
            return max(0.0, min(1.0, similarity))
        except Exception as e:
            print(f"Erreur calcul similarité cosinus: {e}")
            return 0.0
