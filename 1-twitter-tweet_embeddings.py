#!/usr/bin/env python3
"""
What it does

  This script parses and ingests Twitter data from a compressed zip
  file, extracts tweets as JSON objects, processes them for embedding
  in a document repository, and saves the processed documents to disk.
  It uses an Ollama Embeddings model to generate embeddings for each tweet.

Inputs

  A compressed Twitter export file in zip format (input argument "twitterfile")
  An optional default file location for temporary files (defined in config module)

Outputs

  A directory of JSON files containing processed documents, where each
  document represents a tweet with its embedding information
  The script saves the processed documents to disk at the specified
  output location (defined in config module)
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import time
import zipfile

from langchain.docstore.document import Document
from langchain_community.embeddings import OllamaEmbeddings

import config
from utilities import save_doc


def uncompress(twitterfile=False, default_file=False):
    try:
        with zipfile.ZipFile(twitterfile, "r") as z:
            for name in z.namelist():
                if name == "data/tweets.js":
                    print("Exctracting data/tweets.js to {}".format(default_file))
                    with open(default_file, "wb") as f:
                        f.write(z.read(name))

    except IOError:
        print("File not accessible")
        sys.exit(1)


def js_json(default_file=False, json_file=False):
    pattern = "window.YTD.tweets.part0 = \["
    replacement = '{"data": [ '

    # Read the entire content of the file
    with open(default_file, "r", encoding="utf-8") as file:
        file_content = file.read()

    # Use regex to replace the text
    new_content = re.sub(pattern, replacement, file_content)
    new_content += "}"
    # Write the modified content back to the same file
    with open(json_file, "w") as file:
        file.write(new_content)


def parse_tweets(json_file=False):
    with open(json_file, "r", encoding="utf8") as f:
        tweets = f.read()

    json_tweets = json.loads(tweets)

    parsed_tweets = []
    for tweet in json_tweets["data"]:
        parsed_tweets.append(
            [
                datetime.datetime.strptime(
                    tweet["tweet"]["created_at"], "%a %b %d %H:%M:%S %z %Y"
                ),
                tweet["tweet"]["id"],
                tweet["tweet"]["source"],
                tweet["tweet"]["full_text"],
            ]
        )

    print("%s tweets processed." % len(parsed_tweets))
    return parsed_tweets


def make_document(doc_date=False, id_hash=False, content=False):
    return Document(id=id_hash, page_content=content, metadata={"date": doc_date})


if __name__ == "__main__":
    embeddings = OllamaEmbeddings(
        model=config.llm_embeddings_model,
        base_url=config.llm_url,
    )

    argparser = argparse.ArgumentParser(description="Parse and ingest twitter data.")
    argparser.add_argument(
        "twitterfile", help="compressed twitter export in zip format."
    )
    args = argparser.parse_args()

    default_file = "{}/tweets.js".format(config.data_dir)
    json_file = "{}/tweets.json".format(config.data_dir)

    if not os.path.isdir(config.tweet_embeddings_dir):
        os.mkdir(config.tweet_embeddings_dir)

    if not os.path.exists(json_file):
        uncompress(args.twitterfile, default_file=default_file)
        js_json(default_file=default_file, json_file=json_file)

    for item in parse_tweets(json_file=json_file):
        id_hash = hashlib.sha256(
            item[0].strftime("%Y-%m-%d %H:%M:%S").encode("utf-8")
        ).hexdigest()
        out_json_file = f"{config.tweet_embeddings_dir}/{id_hash}.json"

        if not os.path.isfile(out_json_file):
            content = 'On {}, {} tweeted "{}"'.format(
                item[0].strftime("%Y-%m-%d %H:%M:%S"),
                config.your_name,
                item[3].replace("\n", ""),
            )
            document = make_document(
                doc_date=item[0].strftime("%Y-%m-%d %H:%M:%S"),
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
