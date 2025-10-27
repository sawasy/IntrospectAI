import sys
import argparse
import config
import re

from dateutil import parser

from langchain_qdrant import Qdrant
from langchain_community import embeddings
from langchain_community.chat_models import ChatOllama
from langchain.docstore.document import Document
from langchain_community.document_loaders import DirectoryLoader
from langchain_community.chat_models import ChatOllama
from langchain.docstore.document import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter


import langchain

# langchain.debug = True

llm = ChatOllama(model=config.llm_model, base_url=config.llm_url, keep_alive=-1)

embedding_function = embeddings.OllamaEmbeddings(
    model=config.llm_embeddings_model, base_url=config.llm_url
)


# Define the metadata extraction function.
def metadata_func(record: dict, metadata: dict) -> dict:
    if "metadata" in record:
        for k, v in record.get("metadata").items():
            metadata[k] = v

    return metadata

if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="Process a file.")
    argparser.add_argument("directory", help="Specify the directory to be processed")
    args = argparser.parse_args()

    # If the file doesn't exist stop.
    if not args.directory:  # or not os.path.isfile(args.file):
        print("It's not there!")
        sys.exit(1)

    # loader = UnstructuredMarkdownLoader(args.file)
    loader = DirectoryLoader(args.directory, glob="**/*.md")
    data = loader.load()

    # print(data)
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]

    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)


    for item in data:  # [0].page_content.split(". "):  .lstrip('- ')
        # print(item.page_content)
        # print(item.metadata["source"])
        lines = item.page_content.split("\n")
        try:
            date = parser.parse(lines[0], fuzzy=True)
            formatted_date = date.strftime("%B %d, %Y")
        except:
            formatted_datedate = ""
        print(formatted_date)
        split_docs = []

        for doc in re.split(r"\.\s|\!\s|\n", item.page_content):
            document = Document(
                id=item.id,
                page_content=doc,
                metadata={
                    "source": item.metadata["source"],
                    "date": formatted_date,
                    "author": "Matthew Sawasy",
                },
            )

            split_docs.append(document)

        print(split_docs)
        # Convert documents to Embeddings and store them
        vectorstore = Qdrant.from_documents(
            url=config.qdrant_url,
            documents=split_docs,
            collection_name=config.project_name,
            embedding=embedding_function,
        )
