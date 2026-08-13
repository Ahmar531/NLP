import os

from dotenv import load_dotenv
from qdrant_client.models import Distance, VectorParams

from langchain_qdrant import QdrantVectorStore

from app.rag.embeddings import embeddings
from app.rag.qdrant_client import get_client


load_dotenv()

COLLECTION_NAME = os.getenv(
    "QDRANT_COLLECTION",
    "pdf_documents"
)
def initialize_collection():
    """
    Create Qdrant collection if it doesn't exist.
    """

    try:
        existing_collections = [
            collection.name
            for collection in get_client().get_collections().collections
        ]
    except Exception:
        # If the database is not ready yet, let the next call retry.
        return

    if COLLECTION_NAME not in existing_collections:

        get_client().create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=384,
                distance=Distance.COSINE,
            ),
        )


def get_vector_store():

    initialize_collection()

    vector_store = QdrantVectorStore(
        client=get_client(),
        collection_name=COLLECTION_NAME,
        embedding=embeddings,
    )

    return vector_store


def add_documents(documents):

    vector_store = get_vector_store()

    vector_store.add_documents(documents)

    return len(documents)


def search_documents(query: str, k: int = 5):

    vector_store = get_vector_store()

    results = vector_store.similarity_search(
        query,
        k=k,
    )

    return results