#!/usr/bin/env python3

from qdrant_client import QdrantClient

import config

if __name__ == "__main__":
    # Initialize Qdrant client and create a collection if it doesn't exist
    qdrant_client = QdrantClient(
        url=config.qdrant_url,
        api_key=config.qdrant_api_key,
    )

    try:
        qdrant_client.delete_collection(collection_name=config.project_name)
    except Exception as e:
        print(f"Can't delete collection: {e}")
