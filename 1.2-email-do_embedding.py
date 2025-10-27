import argparse
import sqlite3
import sys
import errno
import os
import time
import datetime
import pickle
import json
from typing import Any, Dict, List, Union

from rich.console import Console

from langchain.docstore.document import Document

import config
from utilities import remove_non_ascii, embed_str


def create_tables():
    connection = sqlite3.connect(config.sqlite_email_file)
    cursor = connection.cursor()
    sql = "CREATE TABLE email_embedded (fact_hash TEXT UNIQUE, fact_date TIMESTAMP, msg_from TIMESTAMP, facts TEXT, embeddings BLOB)"
    cursor.execute(sql)
    sql = "CREATE INDEX index_embedded_hash ON email_embedded (fact_hash);"
    cursor.execute(sql)
    connection.close()


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


# CREATE TABLE email_embedded (fact_hash TEXT UNIQUE, fact_date TIMESTAMP, msg_from TIMESTAMP, facts TEXT UNIQUE, embeddings TEXT)
def write_msg_to_db(
    fact_hash: str,
    fact_date: datetime,
    msg_from: str,
    facts: str,
    embeddings: bytes,
    table_name: str,
    connection: sqlite3.Connection,
):
    cursor = connection.cursor()

    # sql = f'INSERT INTO {table_name} (fact_hash, fact_date, msg_from, facts, embeddings) VALUES (?)  (fact_hash, fact_date, msg_from, facts}", "{sqlite3.Binary(embeddings)}")'
    # print(sql)
    sql = f"INSERT INTO {table_name} (fact_hash, fact_date, msg_from, facts, embeddings) VALUES (?, ?, ?, ?, ?)"
    params = (fact_hash, fact_date, msg_from, facts, embeddings)
    try:
        connection.execute(sql, params)
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed:" in e.args:
            print(f"Record already exists. {e}")
            # print(sql)
        else:
            print(e)
    connection.commit()
    cursor.close()


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



def flatten_json_for_embedding(data: Union[Dict, str]) -> str:
    """
    Flattens JSON data into a normalized string format suitable for embedding.
    
    Args:
        data: Either a dictionary or a JSON string to be flattened
        
    Returns:
        A flattened string representation of the JSON data
        
    Example:
        >>> data = {"name": "John", "info": {"age": 30, "skills": ["Python", "JS"]}}
        >>> flatten_json_for_embedding(data)
        'name: John. info age: 30. info skills: Python, JS.'
    """
    
    # Convert string to dict if needed
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON string provided")
    
    def _flatten_dict(d: Dict, parent_key: str = '') -> List[str]:
        items: List[str] = []
        
        for key, value in d.items():
            new_key = f"{parent_key} {key}" if parent_key else key
            
            if isinstance(value, dict):
                items.extend(_flatten_dict(value, new_key))
            elif isinstance(value, list):
                # Handle lists by joining elements with commas
                if all(isinstance(x, (str, int, float, bool)) for x in value):
                    items.append(f"{new_key}: {', '.join(str(x) for x in value)}")
                else:
                    # For complex nested lists, process each item
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            items.extend(_flatten_dict(item, f"{new_key} {i}"))
                        else:
                            items.append(f"{new_key} {i}: {str(item)}")
            else:
                items.append(f"{new_key}: {str(value)}")
                
        return items
    
    # Get flattened items and join them with periods
    flattened = '. '.join(_flatten_dict(data))
    
    # Clean up any double spaces and add final period
    flattened = ' '.join(flattened.split())
    if not flattened.endswith('.'):
        flattened += '.'
        
    return flattened


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

    connection = sqlite3.connect(config.sqlite_email_file)
    if not table_exists(connection=connection, table_name="email_embedded"):
        create_tables()

    sql = "SELECT * FROM email_facts ORDER BY facts DESC;"
    cursor = connection.cursor()

    cursor.execute(sql)
    messages = cursor.fetchall()
    total_files = len(messages)
    print(total_files)
    the_keys = []
    for count, message in enumerate(messages):
        console.print(
            "[dodger_blue1]Processing message {} - {}.".format(
                count, remove_non_ascii(message[1].replace("\r", ""))
            )
        )
        fact_hash=message[0]
        sql = "SELECT 1 FROM email_embedded WHERE fact_hash = ? LIMIT 1"
        cursor.execute(sql, (fact_hash,))
        row_exists = cursor.fetchone() is not None
        if not row_exists:
            total_files -= 1
            start_time = time.perf_counter()
            start_time2 = time.perf_counter()

            json_data = json.loads(message[3])
            if not json_data:
                console.print(f"Skipping. No data. {message[3]}")
            else:
                flat_facts = flatten_json_for_embedding(json_data)
                # print(flat_facts)
                console.print(
                    "[bright_cyan]---------------------------------------------------------------------------------------------"
                )

                embeddings = embed_str(data_point=flat_facts)
                pickled_embeddings = pickle.dumps(embeddings)
                end_time = time.perf_counter()
                elapsed_time = round((end_time - start_time), 3)
                print(f"Writing fact: {message[0]}")
                write_msg_to_db(
                    fact_hash=message[0],
                    fact_date=message[1],
                    msg_from=message[2],
                    facts=message[3],
                    embeddings=pickled_embeddings,
                    table_name="email_embedded",
                    connection=connection,
                )

            end_time2 = time.perf_counter()
            elapsed_time2 = round((end_time2 - start_time2), 3)
            # print(f"Embedding time: {elapsed_time} - Total time: {elapsed_time2} seconds")

            # print(f"Total files left {total_files}.")
            # sys.stdout.write("Files left: %d files   \r" % (total_files))
            # sys.stdout.flush()
    # print(set(the_keys))
