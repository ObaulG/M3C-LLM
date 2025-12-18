
import json
import os
import pickle
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import faiss
from langchain_community.docstore.base import Docstore

from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import create_retriever_tool
from langchain_mistralai import MistralAIEmbeddings, ChatMistralAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

FAISS_DB_PATH = "faiss_index.bin"
FAISS_DOCSTORE_PATH = "index_to_docstore_id.pkl"

if __name__ == "__main__":
    question = "Que peut-on dire de la randonnée en Corse ?"

    llm: BaseChatModel = ChatMistralAI(
        model="mistral-small-2501",
        temperature=0.7,
        max_retries=2,
        mistral_api_key=os.getenv("MISTRAL_API_KEY"),
        # other params...
    )

    embedder = MistralAIEmbeddings(
        model="mistral-embed",
    )

    # Load the FAISS index from the binary file
    index = faiss.read_index(FAISS_DB_PATH)
    with open(FAISS_DOCSTORE_PATH, "rb") as f:
        index_to_docstore_id = pickle.load(f)

    # we must populate the docstore again
    docstore = InMemoryDocstore()
    self.load_all_jsons(docstore)

    self.vector_store = FAISS(
        embedding_function=self.embedder,
        index=index,
        index_to_docstore_id=index_to_docstore_id,
        docstore=docstore,
    )