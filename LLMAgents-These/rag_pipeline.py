import os
import time
from typing import Dict, Optional, List, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI  # Exemple pour Gemini (à installer si nécessaire)
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from pydantic import BaseModel, Field
import rank_bm25
import database

# Listes des modèles (déjà définies)
MISTRAL_MODELS = [
    "ministral-3b-2410", "ministral-8b-2410", "open-mistral-7b", "open-mistral-nemo",
    "mistral-tiny", "mistral-small", "mistral-medium", "mistral-large-2411"
]
GEMINI_MODELS = [
    "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemma-3-1b", "gemma-3-2b",
    "gemma-3-4b", "gemma-3-12b", "gemma-3-27b", "gemini-2.5-flash-live", "gemini-2.0-flash-live"
]


class RetrievalResult(BaseModel):
    """Modèle Pydantic pour décrire le résultat d'une requête RAG."""
    response: str
    model_used: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    error: Optional[str] = None

class RAGSource(BaseModel):
    """Modèle pour une source de document"""
    content: str = Field(..., description="Contenu du document")
    score: float = Field(..., description="Score de pertinence")
    metadata: Dict = Field(..., description="Métadonnées du document (titre, source, etc.)")

class RAGPipeline:

    RAG_template = """
### Contexte
Votre tâche est de répondre aux questions de manière précise, claire et détaillée en vous basant sur les informations fournies dans les extraits de documents ci-dessous.

### Extraits de documents
{context}

### Instructions
1. Utilisez uniquement les informations fournies dans les extraits de documents pour répondre à la question.
2. Si la réponse ne peut pas être déduite des extraits, répondez : "Je n'ai pas assez d'informations pour répondre à cette question."
3. Répondez de manière concise et structurée.
4. Citez les sources des informations utilisées en mentionnant les identifiants des extraits (par exemple, "Source : [Document 1, Page 2]").

### Question
{question}

### Réponse
"""

    def __init__(self):
        """
        Initialise le pipeline RAG v1
        """
        print("\n" + "=" * 60)
        print("INITIALISATION RAG v1 (BASIQUE)")
        print("=" * 60)
        self.dict_llm: dict[str, BaseChatModel] = {}
        self._init_llm_instances()
        self.embedder = MistralAIEmbeddings(model="mistral-embed")
        self.embedder_name = "mistral-embed"
        self.db_connection_factory = database.get_db_connection

        print("\n" + "=" * 60)
        print("Système RAG basique initialisé...")
        print("=" * 60 + "\n")

    async def query_simple(self,
                           prompt: str,
                           model: str,
                           **kwargs) -> tuple[BaseMessage, float]:
        """Asynchronously queries a language model (LLM) with a given prompt and returns its response along with processing time.

        Args:
            prompt (str): The input text or instruction to send to the language model.
            model (str): The identifier or name of the language model to use for the query.
            **kwargs: Additional keyword arguments to pass to the LLM invocation method.
                      These can include parameters like temperature, max_tokens, etc.

        Returns:
            tuple[BaseMessage, float]:
                - BaseMessage: The response object returned by the language model.
                - float: The processing time (in seconds) taken by the LLM to generate the response.
        """
        answer, total_time = await self._invoke_llm(model, prompt)
        return answer, total_time


    async def query_rag(self,
                        prompt:str,
                        model:str,
                        reranking: Optional[str],
                        final_prompt: Optional[str],
                        sources:Optional[List[RAGSource]],
                        k: int = 3,
                        **kwargs) -> tuple[BaseMessage, List[RAGSource], float]:
        """
        if preprocess_data does not contain the keys final_prompt and sources,
        then this function executes the preprocess.
        Then, it calls the LLM invocation method.
        """
        if not (final_prompt or sources):
            final_prompt, sources = await self.rag_preprocess(prompt, reranking, k)

        answer, total_time = await self.query_simple(final_prompt, model, **kwargs)

        return answer, sources, total_time
    def _init_llm_instances(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        for model_name in MISTRAL_MODELS:
            try:
                llm = ChatMistralAI(
                    model_name=model_name,
                    api_key=MISTRAL_API_KEY,
                    temperature=0.7
                )
                self.dict_llm[model_name] = llm
                print(f"Modèle Mistral '{model_name}' initialisé avec succès.")
            except Exception as e:
                print(f"Erreur lors de l'initialisation du modèle Mistral '{model_name}': {e}")

        for model_name in GEMINI_MODELS:
            try:
                llm = ChatGoogleGenerativeAI(
                    model=model_name,
                    api_key=GEMINI_API_KEY,
                )
                self.dict_llm[model_name] = llm
                print(f"Modèle Gemini '{model_name}' initialisé avec succès.")
            except Exception as e:
                print(f"Erreur lors de l'initialisation du modèle Gemini '{model_name}': {e}")

    def _get_prompt_embeddings(self, prompt: str) -> list[float]:
        """
        Transforme le prompt en un vecteur d'embeddings.

        Args:
            prompt (str): Le texte du prompt à transformer.

        Returns:
            list[float]: Le vecteur d'embeddings du prompt.
        """
        try:
            # Utilise le modèle d'embeddings déjà initialisé dans la classe
            embeddings = self.embedder.embed_query(prompt)
            return embeddings
        except Exception as e:
            raise ValueError(f"Erreur lors de la transformation du prompt en embeddings : {e}")

    async def _retrieve_top_k_chunks_from_db(self,
                                       prompt_embeddings: List[float],
                                       k: int = 3) -> List[RAGSource]:
        """
        Recherche les k chunks les plus pertinents dans la base de données PostgreSQL,
        en utilisant la similarité cosinus entre les embeddings.

        Args:
            prompt_embeddings (List[float]): Embeddings du prompt.
            k (int): Nombre de chunks à retourner.

        Returns:
            List[RAGSource]: Liste de tuples (chunk, score) triés par pertinence.
        """

        # c.chunk_id, \
        #     c.document_id, \
        #     c.content, \
        #     c.num_page, \
        #     c.position_in_page, \
        #     c.token_count, \
        #     c.metadata, \
        #     1 - (ce.embedding <= > %s)
        # AS
        # similarity
        print("retrieve_top_k_chunks_from_db")
        aconn = await database.get_db_connection()
        print(aconn)
        async with aconn:
            results = await database.get_top_k_similar_chunks(aconn,
                                                              embedding=prompt_embeddings,
                                                              model_name=self.embedder_name,
                                                              k=k)
        await aconn.close()

        rag_sources = []
        for row in results:
            metadata = {
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "num_page": row["num_page"],
                "position_in_page": row["position_in_page"],
                "token_count": row["token_count"],
                # Ajouter d'autres métadonnées si nécessaire
            }
            # Fusionner les métadonnées existantes (JSON) avec les métadonnées extraites
            if row["metadata"]:
                metadata.update(row["metadata"])

            rag_source = RAGSource(
                content=row["content"],
                score=row["similarity"],
                metadata=metadata
            )
            rag_sources.append(rag_source)

        return rag_sources

    def _build_augmented_prompt(self, initial_prompt: str, sources: List[RAGSource]) -> str:
        chunk_lines = [f"[Document {i}] : {sources[i].content}" for i in range(len(sources))]
        context_string = "\n".join(chunk_lines)
        return self.RAG_template.format(question=initial_prompt, context=context_string)

    def rerank(self,
            sources: List[RAGSource],
            query: str,
            k: int = 4,
            method: Literal["bm25", "bm25+"] = "bm25",
            k1: float = 1.5,
            b: float = 0.75,
            delta: float = 0.5
    ):
        """
        Réorganise une liste de sources de documents selon leur pertinence par rapport à une requête,
        en utilisant BM25 ou BM25+ pour le reranking.
        Note : les scores obtenus sont stockés dans la clef score_bm25.
        sources est retriée **en place**.
        Args:
            sources: Liste de RAGSource à reranker. Chaque source doit contenir un champ `content`.
            query: Requête utilisateur pour laquelle calculer la pertinence.
            k: Nombre de résultats les plus pertinents à retourner. Par défaut, 4.
            method: Méthode de reranking ("bm25" ou "bm25+"). Par défaut, "bm25".
            k1: Paramètre de saturation de terme pour BM25/BM25+. Par défaut, 1.5.
            b: Paramètre de pondération de la longueur du document. Par défaut, 0.75.
            delta: Paramètre spécifique à BM25+ pour ajuster la normalisation de longueur.
                   Par défaut, 0.5.


        """
        if not sources:
            return

        # Extraire les contenus textuels
        corpus = [source.content for source in sources]
        tokenized_corpus = [content.split() for content in corpus]
        tokenized_query = query.split()

        # Choisir la méthode de reranking
        if method == "bm25":
            model = rank_bm25.BM25Okapi(tokenized_corpus, k1=k1, b=b)
        elif method == "bm25+":
            model = rank_bm25.BM25Plus(tokenized_corpus, k1=k1, b=b, delta=delta)
        else:
            print(f"Méthode de reranking non supportée : {method}. Utilise 'bm25' ou 'bm25+'.")
            return

        # Calculer les scores
        scores = model.get_scores(tokenized_query)

        # Mettre à jour les scores des sources
        for i, source in enumerate(sources):
            source.score_bm25 = scores[i]

        # Trier par score décroissant
        sources.sort(key=lambda x: x.score_bm25, reverse=True)
        return

    async def rag_preprocess(self,
                       prompt: str, *
                       reranking: Optional[str],
                       k: int = 3, ) -> tuple[str, List[RAGSource]]:
        """
        Établit les étapes préliminaires du RAG :
        1. Transforme le prompt en embeddings.
        2. Recherche les k chunks les plus pertinents.

        Args:
            prompt (str): Le texte du prompt.
            k (int): Nombre de chunks à retourner.
            reranking (str): optional operation to rerank the documents retrieved with another algorithm
        Returns:
            list: Liste des k chunks les plus pertinents (avec leurs scores et métadonnées).
        """
        print("rag_preprocess")

        try:
            # 1. Transforme le prompt en embeddings
            prompt_embeddings = self._get_prompt_embeddings(prompt)
            print("prompt_embeddings done")
            # 2. Recherche les 10*k chunks les plus pertinents
            top_k_chunks = await self._retrieve_top_k_chunks_from_db(prompt_embeddings, 10*k)
            print("top_k_chunks done")
            # 3. Reranking pour garder k chunks
            print("reranking: {}".format(reranking))
            if reranking:
                self.rerank(top_k_chunks, prompt, k, method=reranking)
            print("reranking done")
            augmented_prompt = self._build_augmented_prompt(prompt, top_k_chunks[:k])
            return augmented_prompt, top_k_chunks[:k]
        except Exception as e:
            raise ValueError(f"Erreur lors du prétraitement RAG : {e}")

    async def _invoke_llm(self, model: str, prompt: str) -> tuple[AIMessage, float]:
        """
        Encapsule ainvoke, en ajoutant le temps d'execution.
        """
        start = time.time()
        answer = await self.dict_llm[model].ainvoke(prompt)
        total_time = time.time() - start

        return answer, total_time
