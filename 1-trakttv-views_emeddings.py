#!/usr/bin/env python3
"""
What it does

  This script loads viewing data from a JSON file into Qdrant
  and generates embeddings for each movie or show item using
  the OllamaEmbeddings model. The script iterates over each
  watched item, creates a document with metadata and content,
  embeds the document using the OllamaEmbeddings model, and
  saves the resulting embedding to a new JSON file.

Inputs

  A single input file in JSON format containing Trakt.tv viewing
  data (specify as a command-line argument)

Outputs

  A series of JSON files in the `trakttv_embeddings_dir` directory,
  each containing an embedding for a movie or show item, along
  with metadata and content information.
"""

import argparse
import hashlib
import os
import sys
import time

from dateutil import parser
from langchain_community.embeddings import OllamaEmbeddings

import config
from utilities import load_json, make_document, save_doc

if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(
        description="Loads Trakt.tv viewing data into qdrant"
    )
    arg_parser.add_argument("input_file", help="Specify the file to be processed")
    args = arg_parser.parse_args()

    # If the file doesn't exist stop.
    if not os.path.isfile(args.input_file):
        print(f"{args.input_file} not found")
        sys.exit(1)

    embeddings = OllamaEmbeddings(
        model=config.llm_embeddings_model,
        base_url=config.llm_url,
    )

    json_blob = load_json(args.input_file)

    for item in json_blob["watched"]:
        if "movie" in item.keys():
            content = "movie"
        if "show" in item.keys():
            content = "show"
        watch_date = parser.parse(item["last_watched_at"], fuzzy=True)
        id_hash = hashlib.sha256(
            f'{item[content]["title"]}-{watch_date}'.encode("utf-8")
        ).hexdigest()
        out_json_file = f"{config.trakttv_embeddings_dir}/{id_hash}.json"

        if not os.path.isfile(out_json_file):
            print(
                f'{watch_date.strftime("%Y-%m-%d %H:%M:%S")} - {item[content]["title"]}'
            )

            content1 = f'Matt last watched the {content} {item[content]["title"]} on {watch_date.strftime("%Y-%m-%d")}.\n'
            content2 = f'Matt has watched the {content} {item[content]["title"]} a total of {item["plays"]} times'
            content = content1 + content2

            document = make_document(
                doc_date=watch_date.strftime("%Y-%m-%d %H:%M:%S"),
                id_hash=id_hash,
                content=content,
            )
            # Start the timer
            start_time = time.perf_counter()
            embedding = embeddings.embed_query(document)
            # End the timer
            end_time = time.perf_counter()

            # Calculate elapsed time
            elapsed_time = round((end_time - start_time), 3)
            print(f"Embedding took: {elapsed_time} seconds")

            document.metadata["embeddings"] = embedding

            save_doc(doc=document, file_path=out_json_file)
        else:
            print("skipping {}".format(out_json_file))
