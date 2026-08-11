from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

import uuid


class LongTermMemory:

    def __init__(self):

        # Local Qdrant database
        self.client = QdrantClient(
            path="./qdrant_data"
        )

        # Embedding model
        self.embeddings = FastEmbedEmbeddings(
            model_name="BAAI/bge-small-en-v1.5"
        )

        # BGE-small = 384 dimensions
        self.vector_size = 384

        self.collection_name = "user_memories"

        # Create collection if it doesn't exist
        collections = self.client.get_collections()

        collection_names = [
            collection.name
            for collection in collections.collections
        ]

        if self.collection_name not in collection_names:

            self.client.create_collection(
                collection_name=self.collection_name,

                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )


    # ==========================================
    # SAVE MEMORY
    # ==========================================

    def save_memory(
        self,
        user_id: str,
        memory: str,
    ):

        vector = self.embeddings.embed_query(
            memory
        )

        point_id = str(uuid.uuid4())

        self.client.upsert(
            collection_name=self.collection_name,

            points=[
                PointStruct(
                    id=point_id,

                    vector=vector,

                    payload={
                        "user_id": user_id,
                        "memory": memory,
                    },
                )
            ],
        )

        return "Memory saved successfully."


    # ==========================================
    # SEARCH MEMORY
    # ==========================================

    def search_memory(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
    ):

        query_vector = self.embeddings.embed_query(
            query
        )

        results = self.client.query_points(

            collection_name=self.collection_name,

            query=query_vector,

            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(
                            value=user_id
                        ),
                    )
                ]
            ),

            limit=limit,

            with_payload=True,
        )

        memories = []

        for result in results.points:

            if result.payload:

                memories.append(
                    result.payload["memory"]
                )

        return memories