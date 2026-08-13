import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient


load_dotenv()


QDRANT_PATH = os.getenv(
    "QDRANT_PATH",
    "./qdrant_data",
)


client = None


def get_client():

    global client

    if client is None:

        # Reuse one local client for the whole app so the same storage folder
        # is not opened by multiple QdrantLocal instances.
        client = QdrantClient(
            path=QDRANT_PATH,
        )

    return client


def close_client():

    global client

    if client is not None:

        try:
            client.close()

        except Exception:
            pass

        finally:
            client = None