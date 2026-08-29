import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import List, Optional

from ai_companion.settings import settings
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass
class Memory:
    """Represents a memory entry in the vector store."""

    text: str
    metadata: dict
    score: Optional[float] = None

    @property
    def id(self) -> Optional[str]:
        return self.metadata.get("id")

    @property
    def user_id(self) -> Optional[str]:
        return self.metadata.get("user_id")

    @property
    def timestamp(self) -> Optional[datetime]:
        ts = self.metadata.get("timestamp")
        return datetime.fromisoformat(ts) if ts else None


class VectorStore:
    """A class to handle vector storage operations using Qdrant."""

    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    COLLECTION_NAME = "long_term_memory"
    SIMILARITY_THRESHOLD = 0.9

    _instance: Optional["VectorStore"] = None
    _initialized: bool = False

    def __new__(cls) -> "VectorStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self.model = SentenceTransformer(self.EMBEDDING_MODEL)
            self._init_client()
            self._initialized = True

    def _init_client(self) -> None:
        """Initialize Qdrant client."""

        # Qdrant Cloud
        if (
            settings.QDRANT_URL
            and settings.QDRANT_URL.startswith(
                ("http://", "https://")
            )
        ):
            try:
                client = QdrantClient(
                    url=settings.QDRANT_URL,
                    api_key=settings.QDRANT_API_KEY,
                    check_compatibility=False,
                )

                client.get_collections()

                self.client = client

                logger.info(
                    f"Connected to remote Qdrant at "
                    f"{settings.QDRANT_URL}"
                )

                if not self._collection_exists():
                    self._create_collection()
                else:
                    self._ensure_payload_index()

                return

            except Exception as e:
                logger.warning(
                    f"Failed to connect to remote Qdrant: {e}"
                )

        # Local persistent Qdrant
        storage_path = settings.LONG_TERM_MEMORY_PATH

        try:
            os.makedirs(
                os.path.abspath(storage_path),
                exist_ok=True,
            )

            self.client = QdrantClient(
                path=storage_path,
                check_version=False,
            )

            logger.info(
                f"Initialized local Qdrant vector store at "
                f"{storage_path}"
            )

            if not self._collection_exists():
                self._create_collection()
            else:
                self._ensure_payload_index()

        except Exception as e:
            logger.error(
                f"Could not initialize local Qdrant at "
                f"{storage_path}: {e}"
            )

            raise RuntimeError(
                "Qdrant persistent storage could not be initialized."
            ) from e

    def _ensure_payload_index(self) -> None:
        """Ensure payload index on user_id exists for fast and valid filtered queries."""
        try:
            self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="user_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            logger.info(
                f"Created keyword payload index for 'user_id' in '{self.COLLECTION_NAME}'"
            )
        except Exception as e:
            logger.debug(f"Payload index check: {e}")

    def _collection_exists(self) -> bool:
        """Check if the memory collection exists."""

        try:
            collections = (
                self.client
                .get_collections()
                .collections
            )

            return any(
                col.name == self.COLLECTION_NAME
                for col in collections
            )

        except Exception as e:
            logger.error(
                f"Error checking collections: {e}"
            )
            return False

    def _create_collection(self) -> None:
        """Create a new collection for storing memories."""

        sample_embedding = self.model.encode(
            "sample text"
        )

        self.client.create_collection(
            collection_name=self.COLLECTION_NAME,
            vectors_config=VectorParams(
                size=len(sample_embedding),
                distance=Distance.COSINE,
            ),
        )

        logger.info(
            f"Created Qdrant collection "
            f"'{self.COLLECTION_NAME}'"
        )
        self._ensure_payload_index()

    def _build_user_filter(
        self,
        user_id: Optional[str]
    ) -> models.Filter:
        """Build Qdrant filter condition for user_id, strictly isolating users."""

        eff_user = str(user_id or "default_user").strip()

        return models.Filter(
            must=[
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(
                        value=eff_user
                    ),
                )
            ]
        )

    def find_similar_memory(
        self,
        text: str,
        user_id: Optional[str] = None
    ) -> Optional[Memory]:
        """Find a similar memory for this user."""

        results = self.search_memories(
            text,
            user_id=user_id,
            k=1
        )

        if (
            results
            and results[0].score is not None
            and results[0].score >= self.SIMILARITY_THRESHOLD
        ):
            return results[0]

        return None

    def store_memory(
        self,
        text: str,
        metadata: dict,
        user_id: Optional[str] = None
    ) -> None:
        """Store a memory for a specific user."""

        if not self._collection_exists():
            self._create_collection()

        effective_user_id = (
            user_id
            or metadata.get("user_id")
            or "default_user"
        )

        metadata["user_id"] = effective_user_id

        similar_memory = self.find_similar_memory(
            text,
            user_id=effective_user_id
        )

        if similar_memory and similar_memory.id:
            point_id = similar_memory.id
            metadata["id"] = point_id
        else:
            point_id = (
                metadata.get("id")
                or str(uuid.uuid4())
            )
            metadata["id"] = point_id

        embedding = self.model.encode(text)

        point = PointStruct(
            id=point_id,
            vector=embedding.tolist(),
            payload={
                "text": text,
                **metadata,
            },
        )

        self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[point],
        )

        logger.info(
            f"Upserted memory point "
            f"id='{point_id}' "
            f"for user='{effective_user_id}': "
            f"'{text}'"
        )

    def search_memories(
        self,
        query: str,
        user_id: Optional[str] = None,
        k: int = 5
    ) -> List[Memory]:
        """Search memories filtered by user_id."""

        if not query or not query.strip():
            return []

        if not self._collection_exists():
            return []

        try:
            query_embedding = self.model.encode(query)

            query_filter = self._build_user_filter(
                user_id
            )

            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.COLLECTION_NAME,
                    query=query_embedding.tolist(),
                    query_filter=query_filter,
                    limit=k,
                )

                points = response.points

            else:
                points = self.client.search(
                    collection_name=self.COLLECTION_NAME,
                    query_vector=query_embedding.tolist(),
                    query_filter=query_filter,
                    limit=k,
                )

            memories = []

            for hit in points:
                payload = hit.payload or {}

                text = payload.get(
                    "text",
                    ""
                )

                if text:
                    memories.append(
                        Memory(
                            text=text,
                            metadata={
                                k: v
                                for k, v in payload.items()
                                if k != "text"
                            },
                            score=hit.score,
                        )
                    )

            return memories

        except Exception as e:
            logger.error(
                f"Error searching memories "
                f"for user='{user_id}': {e}"
            )
            return []

    def get_all_memories(
        self,
        user_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Memory]:
        """Retrieve all memories for a specific user."""

        if not self._collection_exists():
            return []

        try:
            query_filter = self._build_user_filter(
                user_id
            )

            records, _ = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                scroll_filter=query_filter,
                limit=limit,
            )

            memories = []

            for hit in records:
                payload = hit.payload or {}

                text = payload.get(
                    "text",
                    ""
                )

                if text:
                    memories.append(
                        Memory(
                            text=text,
                            metadata={
                                k: v
                                for k, v in payload.items()
                                if k != "text"
                            },
                        )
                    )

            return memories

        except Exception as e:
            logger.error(
                f"Error retrieving memories "
                f"for user='{user_id}': {e}"
            )
            return []


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    """Get or create the VectorStore singleton instance."""

    return VectorStore()