#!/usr/bin/env python3
"""
What it does

This script processes a set of text data files, specifically blog, email,
or journal entries, and generates graph documents based on the content.
The generated graphs are then saved as JSON files.

The script uses a Large Language Model (LLM) to transform the text into
graph structures, where entities mentioned in the text are represented as
nodes, and relationships between these entities are represented as edges.
The script also includes a feature to check the truthiness of certain
statements within the text data.

Inputs

- A directory path containing the fact files to be processed (blog facts, email facts, or journal entries)
- Command-line arguments to specify which type of fact files to process
- An option to enable truthiness checking for statements in the text data

Outputs

- Graph documents representing the entities and relationships mentioned in the text data
- These graph documents are saved as JSON files with a unique SHA-256 hash based on their content
- A console output indicating the number of total files remaining to process, false facts found during truthiness checking, or any errors encountered during processing
"""

import argparse
import hashlib
import os
import sys

from langchain.docstore.document import Document
from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_experimental.llms.ollama_functions import OllamaFunctions
from rich import print
from rich.console import Console

import config
from utilities import gather_files, is_id_in_names, load_json, save_doc

# import langchain


# langchain.debug=True
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
    console = Console()
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
        the_graphs_dir = config.blog_graphs_dir

    if args.email:
        the_facts_dir = config.email_facts_dir
        the_graphs_dir = config.email_graphs_dir

    if args.journal:
        the_facts_dir = config.journal_facts_dir
        the_graphs_dir = config.journal_graphs_dir

    llm2 = OllamaFunctions(model=config.llm_relationship_model, base_url=config.llm_url)

    with console.status("Loading Facts..."):
        all_files, total_files = gather_files(file_path=the_facts_dir)

    my_names = config.your_short_names + [config.your_name] + ["me"]

    for data_file in all_files:
        total_files -= 1
        json_doc = load_json(file_path=data_file)

        for item in json_doc["page_content"].split('. |! |"'):
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
                    console.print(f"[red]False fact: {item}")
                    break

            if not any(name in item for name in config.your_short_names):
                print(f"[red]'{item}' missing name {config.your_short_names}")
                break

            document = Document(
                id=json_doc["id"], page_content=item, metadata=json_doc["metadata"]
            )

            new_hash = hashlib.sha256(document.page_content.encode("utf-8")).hexdigest()
            out_json_file = f"{the_graphs_dir}/{new_hash}.json"

            if not os.path.isfile(out_json_file):
                llm_transformer = LLMGraphTransformer(
                    llm=llm2, node_properties=True, relationship_properties=True
                )

                try:
                    with console.status("Generating graph document..."):
                        graph_documents = llm_transformer.convert_to_graph_documents(
                            [document]
                        )
                    if graph_documents[0].relationships:
                        relationships = []
                        nodes = []
                        for relationship in graph_documents[0].relationships:
                            # use only nodes related to subject of Introspect AI
                            if is_id_in_names(
                                relationship.source.id, my_names
                            ) or is_id_in_names(relationship.target.id, my_names):
                                if is_id_in_names(relationship.source.id, my_names):
                                    relationship.source.id = config.your_name
                                if is_id_in_names(relationship.target.id, my_names):
                                    relationship.target.id = config.your_name
                                nodes.append(relationship.source.id)
                                nodes.append(relationship.target.id)
                                relationships.append(relationship)

                        count = 0
                        for node in graph_documents[0].nodes:
                            if is_id_in_names(node.id, my_names):
                                node.id = config.your_name
                            if node.id not in nodes:
                                del graph_documents[0].nodes[count]
                            count = count + 1
                        graph_documents[0].relationships = relationships
                        save_doc(graph_documents[0], out_json_file)
                except Exception as e:
                    print(e)
            else:
                print("{} exists.".format(out_json_file))
        print(f"{total_files} total files remaining to process...")
