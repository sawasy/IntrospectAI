#!/usr/bin/env python3
"""
What it does:

This Python script is designed to process and add graph documents to a Neo4j database.
It supports processing various types of graph documents, including blog posts, emails,
journals, Trakttv records, and tweets.

The script uses the `langchain_community.graphs` library to interact with the Neo4j database,
and it utilizes the `argparse` library for command-line argument parsing.

Inputs:

- Command-line arguments:
        - `--blog`, `-b`: Specify blog graph documents to be processed
        - `--email`, `-e`: Specify email graph documents to be processed
        - `--journal`, `-j`: Specify memoir graph documents to be processed
        - `--trakttv`, `-t`: Specify Trakttv graph documents to be processed
        - `--tweet`, `-x`: Specify tweet graph documents to be processed
- Graph document files: The script expects to find graph document files in a specified
 directory (configured through the `config` module).

Outputs:

- Graph documents are added to the Neo4j database.
- A log of processed nodes and relationships is printed to the console for each data file.
"""

import argparse
import os
import sys

from langchain_community.graphs import Neo4jGraph
from langchain_community.graphs.graph_document import GraphDocument

import config
from utilities import load_json


# Define the metadata extraction function.
def metadata_func(record: dict, metadata: dict) -> dict:
    if "metadata" in record:
        for k, v in record.get("metadata").items():
            metadata[k] = v

    return metadata


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="Process a file.")
    argparser.add_argument(
        "--blog",
        "-b",
        action="store_true",
        help="Specify blog graph documents to be processed",
    )
    argparser.add_argument(
        "--email",
        "-e",
        action="store_true",
        help="Specify email graph documents to be processed",
    )
    argparser.add_argument(
        "--journal",
        "-j",
        action="store_true",
        help="Specify memoir graph documents to be processed",
    )
    argparser.add_argument(
        "--trakttv",
        "-t",
        action="store_true",
        help="Specify trakttv graph documents to be processed",
    )
    argparser.add_argument(
        "--tweet",
        "-x",
        action="store_true",
        help="Specify tweet graph documents to be processed",
    )
    args = argparser.parse_args()

    if len(sys.argv) == 1:
        argparser.print_help()
        sys.exit(1)

    if args.email:
        the_graphs_dir = config.email_graphs_dir

    graph = Neo4jGraph(
        url=config.neo4j_url,
        username=config.neo4j_login,
        password=config.neo4j_pw,
    )

    all_files = []
    for root, _, files in os.walk(the_graphs_dir):
        for file in files:
            all_files.append(os.path.join(root, file))

    for data_file in all_files:
        json_doc = load_json(file_path=data_file)

        document = GraphDocument(
            nodes=json_doc["nodes"],
            relationships=json_doc["relationships"],
            source=json_doc["source"],
        )

        # Ignore nodes without relationships.
        for item in document.relationships:
            print(f"{item.source.id} -> {item.type} -> {item.target.id}")
            graph.add_graph_documents([document], baseEntityLabel=True)
