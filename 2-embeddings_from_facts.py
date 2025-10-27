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
import hashlib
import os
import re
import sys
import time
from dateutil import parser

from langchain.docstore.document import Document
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import CharacterTextSplitter

import config
from utilities import load_json, save_doc, gather_files





def check_truthiness(fact):
    prompt = """
        You are a professional editor.
        ONLY INFORMATION ABOUT {your_short_name}.
        No commentary.
        {your_short_name} is {your_name}.
        Answer True or False only.
        Answer True or False only.
        Answer True or False only.
        Answer True or False only.
        Answer True or False only.
        Is {your_short_name} the subject of the fact?
        {fact}
        """

    llm = ChatOllama(
        model=config.llm_recheck_model, base_url=config.llm_url, keep_alive=-1
    )

    prompt_template = ChatPromptTemplate.from_template(prompt)
    chain = prompt_template | llm | StrOutputParser()
    torf = chain.invoke(
        {
            "fact": item,
            "your_short_name": config.your_short_names[0],
            "your_name": config.your_name,
        }
    )

    return torf


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

    embeddings = OllamaEmbeddings(
        model=config.llm_embeddings_model,
        base_url=config.llm_url,
    )

    all_files, total_files = gather_files(file_path=the_facts_dir)

    for data_file in all_files:
        total_files -= 1
        json_doc = load_json(file_path=data_file)
        formatted_date = parser.parse(json_doc["metadata"]["date"], fuzzy=True).strftime("%Y-%m-%d")

        for item in re.split(r"\.\s|\!\s|\n", json_doc["page_content"]):
        # for item in json_doc["page_content"].split('. |! |"'):
            if args.truthy:
                truth = check_truthiness(fact=item)
                if truth.lower().strip() not in [
                    "true",
                    "1",
                    "t",
                    "y",
                    "yes",
                    "yeah",
                    "yup",
                    "certainly",
                    "uh-huh",
                ]:
                    print(f"False fact: {item}")
                    break

            if not any(name in item for name in config.your_short_names):
                print(f"'{item}' missing name {config.your_short_names}")
                break

            document = Document(
                id=json_doc["id"], page_content=f"This fact was recorded on {formatted_date} - {item}", metadata=json_doc["metadata"]
            )

            new_hash = hashlib.sha256(document.page_content.encode("utf-8")).hexdigest()
            out_json_file = f"{the_embeddings_dir}/{new_hash}.json"

            if not os.path.isfile(out_json_file):
                start_time = time.perf_counter()
                start_time2 = time.perf_counter()

                embedding = embeddings.embed_query(document)

                end_time = time.perf_counter()
                elapsed_time = round((end_time - start_time), 3)

                document.metadata["embeddings"] = embedding

                save_doc(doc=document, file_path=out_json_file)

                end_time2 = time.perf_counter()
                elapsed_time2 = round((end_time2 - start_time2), 3)
                print(
                    f"Embedding time: {elapsed_time} - Total time: {elapsed_time2} seconds"
                )

            # print(f"Total files left {total_files}.")
            sys.stdout.write("Files left: %d files   \r" % (total_files))
            sys.stdout.flush()

    print("Done!")
