import getpass
import json
import os
import logging

import numpy as np
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_core.messages import HumanMessage
from langchain_mistralai.chat_models import ChatMistralAI
import getpass

from mistral_common.protocol.instruct.messages import (
    UserMessage,
)
from mistral_common.protocol.instruct.request import ChatCompletionRequest
from mistral_common.protocol.instruct.tool_calls import (
    Function,
    Tool,
)

from langchain_community.document_loaders import PyPDFLoader

from mistral_common.tokens.tokenizers.mistral import MistralTokenizer
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_core.vectorstores import InMemoryVectorStore
from langchain_community.vectorstores import Chroma

import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS

CHUNK_SIZE_BASE = 800

DOCUMENTS_PATH = "documents"
rag_locations = ["documents/test-m3c"]
embeddings_database_path = "embeddings"

llm = ChatMistralAI(
    model="mistral-medium-latest",
    temperature=0.7,
    max_retries=2,
    mistral_api_key=os.getenv("MISTRAL_API_KEY"),
    # other params...
)

embedder = MistralAIEmbeddings(
    model="mistral-embed",
)


def embedding_function(texts):
    return embedder.embed_documents(texts)


if __name__ == '__main__':
    embed_test = embedder.embed_documents(["get embed size"])
    print(f"Embedding size: {len(embed_test[0])}")
    embedding_size = len(embed_test[0])

    # Create the embeddings (if not already done)

    # document_name: list[list[float]]
    embeddings = {}

    tokenizer = MistralTokenizer.v3(is_tekken=True)
    model_name = "mistral-small-latest"
    tokenizer = MistralTokenizer.from_model(model_name)

    index = faiss.IndexFlatL2(embedding_size)

    vector_store = FAISS(
        embedding_function=embedder,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
    )

    #https://dev.to/eteimz/understanding-langchains-recursivecharactertextsplitter-2846

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE_BASE,
                                                   chunk_overlap=100)

    print("Curr dir: {}".format(os.getcwd()))

    documents_created = 0
    for f in rag_locations:
        # f is a pathname of a folder containing files or folders
        loc = os.path.join(os.getcwd(), f)
        files = os.listdir(loc)
        for d in files:
            path = os.path.join(loc, d)
            if os.path.isdir(path):
                continue

            print(f"Chargement de {d}")
            loader = PyPDFLoader(path)

            try:
                documents = loader.load()
            except Exception as e:
                print(f"Erreur lors du chargement de {d}: {e}")
                continue

            # Découpage en chunks
            texts = text_splitter.split_documents(documents)
            print(f"{d} découpé en {len(texts)} chunks")
            print(texts[0])


            # Construction d'ids stables
            prefix = os.path.splitext(d)[0]
            faiss_ids = [documents_created+i for i in range(len(texts))]
            text_full_ids = [f"{prefix}-{i}" for i in range(len(texts))]

            # Création d'embbedings (vector_store configuré avec l'embedding_function)
            faiss_chunk_ids = vector_store.add_documents(documents=texts, ids=text_full_ids)
            print(f"{len(faiss_chunk_ids)} embeddings créés pour {d}")
            # Prepare chunks data for JSON (1 json/ pdf document)
            chunks_data = {
                "document_id": d,
                "first_faiss_chunk_id": documents_created,
                "chunks": {
                        id_: {
                            "content": text.page_content,
                            "num_page": text.metadata['page'],
                        }
                        for i, (id_, text) in enumerate(zip(text_full_ids, texts))
                }
            }

            output_path = os.path.join("documents/json_chunks", f"{prefix}_chunks.json")
            with open(output_path, "w", encoding="utf-8") as f_out:
                json.dump(chunks_data, f_out, ensure_ascii=False, indent=2)

            print(f"Saved {len(faiss_ids)} chunks for {d} to {output_path}")
            documents_created += len(faiss_ids)

    print("Embeddings created")
    faiss.write_index(index, "faiss_index.bin")
    # If you have additional data like index_to_docstore_id, save it as well
    import pickle

    with open("index_to_docstore_id.pkl", "wb") as f:
        pickle.dump(vector_store.index_to_docstore_id, f)




