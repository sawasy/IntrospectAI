#!/usr/bin/env python3
"""
What it does

This script is designed to process and upload embeddings from various data sources into a Qdrant client.
It supports processing blog, email, journal, trakttv, and tweet embeddings, each of which can be specified
through command-line arguments.

Here's an overview of the steps:

1. The script initializes a Qdrant client with the provided URL and API key.
2. If a collection with the specified project name does not exist in Qdrant, it creates one using the
recommended vector size and distance metric (COSINE).
3. It then gathers all files from the specified directory, which contains embeddings for each data source.
4. For each file, the script loads the JSON data, creates a `Document` object, and adds the vector
to Qdrant's collection.

Inputs

- Command-line arguments:
        - `--blog`, `-b`: Process blog embeddings
        - `--email`, `-e`: Process email embeddings
        - `--journal`, `-j`: Process journal embeddings
        - `--trakttv`, `-t`: Process trakttv embeddings
        - `--tweet`, `-x`: Process tweet embeddings
- Configuration files:
        - `config.py`: Contains configuration settings, such as Qdrant URL and API key,
      embedding directory paths, etc.
- Directory path: The specified directory containing embeddings for each data source

Outputs

- Successfully uploaded vectors to Qdrant's collection
- A collection with the specified project name is created in Qdrant if it did not exist before
- Console output indicating the number of files left to process
"""

import argparse
import os
import sys
import uuid

from langchain.docstore.document import Document
from qdrant_client import QdrantClient, models
from qdrant_client.models import PointStruct

import config
from utilities import load_json


def gather_files(file_path=False):
    all_files = []
    for root, _, files in os.walk(file_path):
        total_files = len(files)
        for file in files:
            all_files.append(os.path.join(root, file))

    return all_files, total_files


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="Process a file.")
    argparser.add_argument(
        "--blog",
        "-b",
        action="store_true",
        help="Specify blog embeddings to be processed",
    )
    argparser.add_argument(
        "--email",
        "-e",
        action="store_true",
        help="Specify email embeddings to be processed",
    )
    argparser.add_argument(
        "--journal",
        "-j",
        action="store_true",
        help="Specify memoir embeddings to be processed",
    )
    argparser.add_argument(
        "--trakttv",
        "-t",
        action="store_true",
        help="Specify trakttv embeddings to be processed",
    )
    argparser.add_argument(
        "--tweet",
        "-x",
        action="store_true",
        help="Specify tweet embeddings to be processed",
    )
    args = argparser.parse_args()

    if len(sys.argv) == 1:
        argparser.print_help()
        sys.exit(1)

    if args.blog:
        the_embeddings_dir = config.blog_embeddings_dir

    if args.email:
        the_embeddings_dir = config.email_embeddings_dir

    if args.journal:
        the_embeddings_dir = config.journal_embeddings_dir

    if args.trakttv:
        the_embeddings_dir = config.trakttv_embeddings_dir

    if args.tweet:
        the_embeddings_dir = config.tweet_embeddings_dir

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

    all_files, total_files = gather_files(file_path=the_embeddings_dir)

    for data_file in all_files:
        # print(data_file)
        total_files -= 1
        try:
            json_doc = load_json(file_path=data_file)
        except:
            print(data_file)
        document = Document(
            id=json_doc["id"],
            page_content=json_doc["page_content"],
            metadata=json_doc["metadata"],
        )

        # Add the vector to Qdrant
        qdrant_client.upsert(
            config.project_name,
            [
                PointStruct(
                    id=str(uuid.uuid4()),
                    payload={"page_content": json_doc["page_content"]},
                    vector=json_doc["metadata"]["embeddings"],
                )
            ],
        )

        # print(f"Total files left {total_files}.")
        sys.stdout.write("Files left: %d files   \r" % (total_files))
        sys.stdout.flush()

    print("Done!")
