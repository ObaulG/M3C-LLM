def __init__(
    self,
    faiss_path: str = FAISS_DB_PATH,
    faiss_doc_store: str = FAISS_DOCSTORE_PATH,
):
    """
    Initialise le pipeline RAG v1

    Args:
        openai_api_key: Clé API OpenAI
        chroma_path: Chemin vers la base ChromaDB
        collection_name: Nom de la collection ChromaDB
        llm_model: Modèle LLM à utiliser
        embedding_model: Modèle d'embeddings (par défaut e5-base-v2)
    """
    print("\n" + "="*60)
    print("INITIALISATION RAG v1 (BASIQUE)")
    print("="*60)
    self.dict_llm: dict[str, BaseChatModel] = {}
    self.init_LLM_instances()
    self.embedder = MistralAIEmbeddings(model="mistral-embed")

    # Load the FAISS index from the binary file.
    # it maps FAISS id to its document's id {filename}-{n_chunk}
    index = faiss.read_index(faiss_path)
    with open(faiss_doc_store, "rb") as f:
        index_to_docstore_id = pickle.load(f)
    print("index_to_docstore_id retrieved")

    # we must populate the docstore again
    self.vector_store = FAISS(
        embedding_function=self.embedder,
        index=index,
        index_to_docstore_id=index_to_docstore_id,
        docstore=InMemoryDocstore(),
    )
    self.load_all_jsons(self.vector_store)

    print("\n" + "="*60)
    print("Système RAG basique initialisé...")
    print("="*60 + "\n")