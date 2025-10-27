import json
import os
import re
import time
import unicodedata
from email_validator import validate_email, EmailNotValidError

from typing import List, Tuple
from dateutil.parser import parse
from email.utils import getaddresses

from langchain.docstore.document import Document
from langchain_ollama import OllamaEmbeddings

import config
import utilities


def remove_blank_lines(input_string):
    # Split the input string into lines
    lines = input_string.splitlines()
    # Filter out lines that are blank or contain only whitespace
    non_blank_lines = [line for line in lines if line.strip()]
    # Join the non-blank lines back into a single string
    result = "\n".join(non_blank_lines)
    return result


def save_doc(doc, file_path=False):
    with open(file_path, "w") as f:
        f.write(doc.json())
    f.close()


def remove_non_ascii(text):
    """Remove non-ASCII characters from the given text."""
    return "".join([i if ord(i) < 128 else "?" for i in text])


def remove_null_chars(s):
    return re.sub(r"\x00", "", s)


def parse_people(message: dict) -> Tuple[str, str]:
    # These are not useful messages generally
    junk = ["undisclosed", "suppressed", "[*to]"]
    # print(f"Util: To {message['To']}")

    # So damn many edge cases...
    pattern = r"[a-zA-Z0-9\[\]\.,\-+_=]+@[a-zA-Z0-9\.\-+_]+"
    # pattern = r"[a-zA-Z0-9\.\-+_=]+@[a-zA-Z0-9\.\-+_]+"
    if (
        message["To"] is not None
        and message["To"] != ""
        and not any(x in message["To"].lower() for x in junk)
    ):
        receiver = re.findall(pattern, message["To"])[0]
    else:
        receiver = "broked_receiver@example.com"

    if not isinstance(message["From"], str):
        sender = "broken_sender@example.com"
    elif not re.findall(
        r"[a-zA-Z0-9\.\-+_]+@[a-zA-Z0-9\.\-+_]+",
        utilities.remove_non_ascii(message["From"]),
    ):
        sender = "broked_sender@example.com"
    else:
        sender = re.findall(
            r"[a-zA-Z0-9\.\-+_]+@[a-zA-Z0-9\.\-+_]+",
            utilities.remove_non_ascii(message["From"]),
        )[0].lower()

    print(f"Util: From {message['From']} -> {sender}")
    print(f"Util: To {message['To']} -> {receiver}")

    return sender, receiver

def parse_people2(message: dict) -> Tuple[str, str]:
    # These are not useful messages generally
    junk = ["undisclosed", "suppressed", "[*to]"]

    receiver = clean_address_list(getaddresses([message.get('to','')]))
    sender = clean_address_list(getaddresses([message.get('from','')]))

    #Email is such dirty data.
    if len(receiver) <= 1:
        if not receiver or any(x in receiver[0][1].lower() for x in junk) or receiver[0][1].count("<") > 1:
            receiver = [("Junk Receiver", "broked_receiver@example.com")]


    if len(sender) <= 1:
        #The count is just to clean up dirty edge cases of <elance <elance no-reply@elance.com>> kind of senders.
        if not sender or any(x in sender[0][1].lower() for x in junk) or sender[0][1].count("<") > 1:
            sender = [("Junk Sender", "broked_sender@example.com")]

    try:
        emailinfo = validate_email(sender[0][1], check_deliverability=False)
        # email = emailinfo.normalized
        # print(email)
    except EmailNotValidError as e:
    # The exception message is human-readable explanation of why it's
    # not a valid (or deliverable) email address.
        print(str(e))
        sender = [("Junk Receiver", "broked_receiver@example.com")]

    # print(f"Util: From {message['From']} -> {sender}")
    # print(f"Util: To {message['To']} -> {receiver}")

    return sender, receiver


def timer(func):
    def wrap_the_func():
        start_time = time.perf_counter()

        func()

        end_time = time.perf_counter()
        elapsed_time = round((end_time - start_time), 3)
        print(elapsed_time)

    return wrap_the_func


def load_json(file_path: str):
    with open(file_path, "r") as file:
        # Load the JSON data from the file
        return json.load(file)


def make_document(doc_date: str, id_hash: str, content: str) -> Document:
    return Document(id=id_hash, page_content=content, metadata={"date": doc_date})


def is_id_in_names(id: str, names: list) -> bool:
    """Check if the given ID (as string) or any of its variations (lowercase) is in the list of names."""
    return id.lower() in [name.lower() for name in names]


def gather_files(file_path: str) -> Tuple[List[str], int]:
    all_files: List[str] = []
    total_files: int = 0

    for root, _, files in os.walk(file_path):
        total_files = len(files)
        for file in files:
            all_files.append(os.path.join(root, file))

    return all_files, total_files


def clean_facts(facts: str) -> List[str]:
    parsed_facts = []

    # for fact in re.split(r"\.\s|\!\s|\n", facts.strip().replace('"', "'").replace("•", "").lstrip('-').strip()):
    for fact in facts.replace('"', "'").replace("•", "").split("\n"):
        # Split the string at the first occurrence of " - "
        parts = fact.split(" - ", maxsplit=1)
        if len(parts) == 2:
            dt_str, rest_of_string = (
                parts[0],
                parts[1].strip(),
            )  # Remove leading spaces after dash

            try:
                # Parse the extracted date-time string
                dt = parse(dt_str)
            except ValueError as e:
                # print(e)
                print(f"'{fact}' missing date")
                pass  # If parsing fails, move on

                # Check if the remaining string starts with any name in the list
            for name in config.your_short_names:
                if rest_of_string.startswith(f"{name}"):
                    parsed_facts.append(fact)
                else:
                    print(f"'{fact}' missing name {config.your_short_names}")

        # if not any(fact.startswith(name) for name in config.your_short_names):
        #     print(f"'{fact}' missing name {config.your_short_names}")
        #     break
        # else:
        #     parsed_facts.append(fact)

    print(parsed_facts)
    return parsed_facts


def table_exists(connection, table_name):
    # Connect to the SQLite database
    cursor = connection.cursor()

    # Query to check if the table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    )

    # Fetch one result
    result = cursor.fetchone()

    # Return True if the table exists, False otherwise
    return result is not None


def embed_str(data_point: str) -> List[str]:
    embedding_llm = OllamaEmbeddings(
        model=config.llm_embeddings_model,
        base_url=config.llm_url,
    )

    return embedding_llm.embed_query(data_point)


def clean_address_list(address_tuples):
    """
    Clean a list of (display_name, email) tuples from getaddresses.
    Handles multiple nested and unmatched quotes in display names.
    
    Args:
        address_tuples: List of tuples from getaddresses
    
    Returns:
        list: List of cleaned tuples in same format
    """
    if not address_tuples:
        return []
    
    cleaned_addresses = []
    
    for display_name, email in address_tuples:
        try:
            # Clean display name
            if display_name:
                # First normalize any unicode
                normalized = unicodedata.normalize('NFKD', str(display_name))
                # Remove all quotes (matched or unmatched)
                display_name = re.sub(r'[\"\']+', '', normalized)
                display_name = display_name.encode('ascii', 'ignore').decode('ascii').strip()
                
            # Clean email
            if email:
                normalized = unicodedata.normalize('NFKD', str(email))
                email = normalized.encode('ascii', 'ignore').decode('ascii').strip().lower()
                
            # Only add if we have at least an email
            if email:
                cleaned_addresses.append((display_name, email))
            
        except Exception as e:
            # Fallback to basic ASCII conversion
            try:
                display_name = re.sub(r'[\"\']+', '', str(display_name))
                display_name = display_name.encode('ascii', 'ignore').decode('ascii').strip()
                email = str(email).encode('ascii', 'ignore').decode('ascii').strip().lower()
                if email:
                    cleaned_addresses.append((display_name, email))
            except:
                continue
    
    return cleaned_addresses

