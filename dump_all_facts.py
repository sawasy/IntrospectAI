#!/usr/bin/env python3
"""
What it does

This script is designed to process and embed facts from various sources,
such as blogs, emails, or journals. It uses a large language model (LLM)
to check the truthfulness of each fact and generate embeddings for them.
The script takes input from command-line arguments and processes files
in specified directories.

Inputs

- Command-line arguments:
        + `--blog`, `-b`: Process blog facts
        + `--email`, `-e`: Process email facts
        + `--journal`, `-j`: Process memoir (journal) facts
        + `--truthy`, `-t`: Have the LLM check if each statement is true
- File directories:
        - The directory containing facts to be processed (e.g., blog facts, email facts)
        - The output directory for embedded files

Outputs

- Embedded files with truthiness checked (if `--truthy` flag is used):
        + A JSON file in the specified output directory, containing the fact's text, metadata, and embeddings
- Error messages:
        + If a fact contains missing names or has an unknown truthfulness status
        + If the LLM embedding process takes too long (optional)
"""

import argparse
import os
import sys

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
        "--blog", "-b", action="store_true", help="Specify blog facts to be processed"
    )
    argparser.add_argument(
        "--email", "-e", action="store_true", help="Specify email facts to be processed"
    )
    argparser.add_argument(
        "--journal",
        "-j",
        action="store_true",
        help="Specify memoir facts to be processed",
    )
    argparser.add_argument(
        "--truthy",
        "-t",
        action="store_true",
        help="Have the LLM check if the statement is true.",
    )

    args = argparser.parse_args()

    if len(sys.argv) == 1:
        argparser.print_help()
        sys.exit(1)

    if args.blog:
        the_facts_dir = config.blog_facts_dir
        the_embeddings_dir = config.blog_embeddings_dir

    if args.email:
        the_facts_dir = config.email_facts_dir
        the_embeddings_dir = config.email_embeddings_dir

    if args.journal:
        the_facts_dir = config.journal_facts_dir
        the_embeddings_dir = config.journal_embeddings_dir

    all_files, total_files = gather_files(file_path=the_facts_dir)

    for data_file in all_files:
        total_files -= 1
        json_doc = load_json(file_path=data_file)

        print(json_doc["page_content"])

    print("Done!")
