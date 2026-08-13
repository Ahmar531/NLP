from uuid import uuid4

from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from langchain_community.embeddings import FastEmbedEmbeddings

from app.rag.qdrant_client import get_client, close_client


MEMORY_COLLECTION = "user_memory"


# ============================================================
# EMBEDDING MODEL
# ============================================================

embeddings = FastEmbedEmbeddings(
    model_name="BAAI/bge-small-en-v1.5"
)


# ============================================================
# CREATE COLLECTION
# ============================================================

def ensure_memory_collection():

    client = get_client()

    collections = client.get_collections()

    existing_collections = [
        collection.name
        for collection in collections.collections
    ]

    if MEMORY_COLLECTION not in existing_collections:

        vector_size = len(
            embeddings.embed_query("test")
        )

        client.create_collection(
            collection_name=MEMORY_COLLECTION,

            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )


# ============================================================
# SAVE / UPDATE MEMORY
# ============================================================

def save_memory(
    user_id: str,
    key: str,
    value: str,
):

    ensure_memory_collection()

    client = get_client()

    # --------------------------------------------
    # Delete old memory with same user_id + key
    # --------------------------------------------

    client.delete(
        collection_name=MEMORY_COLLECTION,

        points_selector=Filter(
            must=[
                FieldCondition(
                    key="user_id",
                    match=MatchValue(
                        value=user_id
                    ),
                ),
                FieldCondition(
                    key="key",
                    match=MatchValue(
                        value=key
                    ),
                ),
            ]
        ),
    )

    # --------------------------------------------
    # Create new embedding
    # --------------------------------------------

    text = f"{key}: {value}"

    vector = embeddings.embed_query(text)

    # --------------------------------------------
    # Store new memory
    # --------------------------------------------

    point = PointStruct(
        id=str(uuid4()),

        vector=vector,

        payload={
            "user_id": user_id,
            "key": key,
            "value": value,
            "text": text,
        },
    )

    client.upsert(
        collection_name=MEMORY_COLLECTION,

        points=[point],
    )


# ============================================================
# GET ONE MEMORY
# ============================================================

def get_memory(
    user_id: str,
    key: str,
):

    ensure_memory_collection()

    client = get_client()

    results = client.scroll(
        collection_name=MEMORY_COLLECTION,

        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="user_id",
                    match=MatchValue(
                        value=user_id
                    ),
                ),
                FieldCondition(
                    key="key",
                    match=MatchValue(
                        value=key
                    ),
                ),
            ]
        ),

        limit=1,
    )

    points = results[0]

    if not points:
        return None

    return points[0].payload.get("value")


# ============================================================
# GET ALL MEMORIES
# ============================================================

def get_all_memories(
    user_id: str,
):

    ensure_memory_collection()

    client = get_client()

    results = client.scroll(
        collection_name=MEMORY_COLLECTION,

        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="user_id",
                    match=MatchValue(
                        value=user_id
                    ),
                ),
            ]
        ),

        limit=100,
    )

    points = results[0]

    memories = []

    for point in points:

        payload = point.payload

        memories.append(
            {
                "key": payload.get("key"),
                "value": payload.get("value"),
            }
        )

    return memories


# ============================================================
# CLOSE CLIENT
# ============================================================

def close_memory_client():

    close_client()