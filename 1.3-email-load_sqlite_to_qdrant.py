import argparse
import sqlite3
import sys
import errno
import os
import pickle
import uuid

from qdrant_client.models import PointStruct
from qdrant_client import QdrantClient, models

from rich.console import Console
from langchain.docstore.document import Document

import config


def make_doc(
    message_hash: str, facts: str, sender: str, receiver: str, date: str
) -> Document:
    document = Document(
        id=message_hash,
        page_content=facts,
        metadata={
            "source": "local",
            "sender": sender,
            "receiver": receiver,
            "date": date,
        },
    )
    return document


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="Process email from sqlite.")
    argparser.add_argument(
        "--debug", "-d", help="Enable Debugging", action="store_true"
    )
    argparser.add_argument(
        "--verbose", "-v", help="Increase Verbosity of output", action="store_true"
    )
    args = argparser.parse_args()

    # If the file doesn't exist stop.
    if not os.path.isfile(config.sqlite_email_file):
        print(f"{args.input_file} not found")
        sys.exit(errno.EINVAL)

    console = Console()
    console.clear()

    documents = []

    # Initialize Qdrant client and create a collection if it doesn't exist
    qdrant_client = QdrantClient(
        url=config.qdrant_url,
        api_key=config.qdrant_api_key,
    )

    try:
        qdrant_client.create_collection(
            collection_name=config.project_name,
            vectors_config=models.VectorParams(
                size=768, distance=models.Distance.COSINE
            ),
        )
    except Exception as e:
        print(f"Collection already exists: {e}")

    connection = sqlite3.connect(config.sqlite_email_file)

    sql = "SELECT * FROM email_embedded ORDER BY fact_date ASC;"
    cursor = connection.cursor()

    cursor.execute(sql)
    messages = cursor.fetchall()
    total_files = len(messages)
    print(total_files)
    for count, message in enumerate(messages):
        total_files -= 1
        embedded_fact = [*message]
        embeddings = pickle.loads(message[4])
        # Add the vector to Qdrant
        qdrant_client.upsert(
            config.project_name,
            [
                PointStruct(
                    id=str(uuid.uuid4()),
                    payload={
                        "page_content": f"This fact was recorded on {embedded_fact[1]} - {embedded_fact[3]}"
                    },
                    vector=embeddings,
                )
            ],
        )
        sys.stdout.write("Files left: %d facts   \r" % (total_files))
        sys.stdout.flush()

    print("Done!")
