#!/usr/bin/env python3
"""
What it does:

This script is designed to process a mail file (.mbox) and extract facts
about individuals mentioned in the messages. It uses a large language model (LLM)
to generate facts based on the context of each message.

The script takes a mail file as input, processes each email, and generates a
set of facts about the sender and receiver using the LLM. The facts are then
written to a JSON file for storage.

Inputs:

- A mail file (.mbox) containing email messages
- An optional command-line argument `--takeout` or `-t` to indicate that the
  input file is a Takeout file

Outputs:

- A set of JSON files containing facts about individuals mentioned in the emails,
 stored in the directory specified by the `email_facts_dir` configuration variable.
Each JSON file contains a single fact about an individual, and the filename is based
on the SHA-256 hash of the sender's email address.
"""

import argparse
import errno
import hashlib
import sqlite3
import os
import sys
import datetime
import json
import time

from dateutil import parser

from rich import print
from rich.console import Console
from rich.style import Style

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

import config
from utilities import remove_non_ascii, remove_blank_lines, clean_facts, table_exists


def create_tables():
    connection = sqlite3.connect(config.sqlite_email_file)
    cursor = connection.cursor()
    sql = "CREATE TABLE email_facts (fact_hash TEXT UNIQUE, fact_date TIMESTAMP, msg_from TIMESTAMP, facts TEXT)"
    cursor.execute(sql)
    sql = "CREATE INDEX index_fact_hash ON email_facts (fact_hash);"
    cursor.execute(sql)
    connection.close()


def do_facts(
    message: str, msg_date: datetime, subject: str, sender: str, receiver: str
) -> str:
    llm = ChatOllama(
        model=config.llm_facts_model, base_url=config.llm_url, keep_alive=-1
    )

    prompt = [
        HumanMessage(
            content=f"""
You are an AI that extracts information from an email to understand *{config.your_name}* better.  Focus on what the email reveals about {config.your_name}'s thoughts, feelings, motivations, characteristics, *and factual information about their interests, hobbies, preferences, and personal details*.

We know that {config.your_name} uses the following emails {config.emails_dict}.  These email addresses are known facts and do not need to be restated. Use these to help determine if a mentioned email address refers to {config.your_name} or someone else.

Analyze the following email and extract information that helps understand {config.your_name}.  Return the output as a JSON object where each piece of information is categorized under a type (e.g., "Thought", "Feeling", "Motivation", "Characteristic", "Value", "Learning", "AreaForImprovement", "Hobby", "Interest", "Preference", "PersonalDetail").  If no relevant insights or facts about {config.your_name} are found, return an empty JSON object `{{}}`.

For each insight or fact, *always include the source*. This can be the sender, recipient, subject, or a specific part of the email body.  Use a "source" key in the JSON object alongside the "type" and the information itself (e.g., "insight" or "fact").

Include the message date in every finding.

*Specific Instructions for Information Types:*

* **Thought:** A specific thought or belief expressed or implied by {config.your_name}.
* **Feeling:** An emotion expressed or implied by {config.your_name}.
* **Motivation:** A reason or driving force behind {config.your_name}'s actions or decisions.
* **Characteristic:** A quality or trait of {config.your_name}'s personality or behavior.
* **Value:** A principle or belief that is important to {config.your_name}.
* **Learning:** Something {config.your_name} has learned or is trying to learn.
* **AreaForImprovement:** An area where {config.your_name} identifies a need for personal or professional development.
* **Hobby:** An activity {config.your_name} enjoys doing regularly for leisure. Example: "Enjoys playing guitar."
* **Interest:** Something that {config.your_name} finds intellectually stimulating or engaging. Example: "Interested in learning about artificial intelligence."
* **Preference:** Something that {config.your_name} likes or dislikes. Example: "Prefers coffee over tea."
* **PersonalDetail:**  A factual piece of information about {config.your_name}, such as "Lives in London", "Is a member of the local hiking club", "loves dogs", "is a vegetarian".  Be cautious about extracting extremely sensitive information unless it is explicitly stated.

Focus on inferring these internal aspects and extracting factual details from the email's content.  If the email only describes external events without revealing anything about {config.your_name}'s internal state or factual details, return an empty JSON object.

Email:

Sender: {sender}
Recipient: {receiver}
Date: {msg_date}
Subject: {subject}
Body: 
{message}
    """
        )
    ]

    data = llm.invoke(prompt)
    return data.content



def write_msg_to_db(
    fact_hash: str,
    fact_date: datetime,
    msg_from: str,
    facts: str,
    table_name: str,
    connection: sqlite3.Connection,
):
    cursor = connection.cursor()

    sql = f"INSERT INTO {table_name} (fact_hash, fact_date, msg_from, facts) VALUES (?, ?, ?, ?)"
    params = (fact_hash, fact_date, msg_from, facts)
    try:
        connection.execute(sql, params)
    except sqlite3.IntegrityError as e:
        print(e.args)
        if "UNIQUE constraint failed:" in e.args[0]:
            print(f"Record already exists. {e} - {fact_hash}")
        else:
            print(e)
    connection.commit()
    cursor.close()


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

    error_style = Style(color="dark_green", bold=True)          # Closest to Moss Green (#556B2F)
    success_style = Style(color="light_goldenrod3")             # Closest to Golden Beige (#D2B48C)
    info_style = Style(color="orange4", bold=True)             # Closest to Deep Brown (#8B4513)
    line_style = Style(color="sky_blue1", dim=True)             # Closest to Sky Blue (#87CEEB)



    documents = []

    connection = sqlite3.connect(config.sqlite_email_file)
    if not table_exists(connection=connection, table_name="email_facts"):
        create_tables()

    if args.debug:
        import langchain

        langchain.debug = True

    sql = "SELECT * FROM msgs ORDER BY msg_date DESC;"
    cursor = connection.cursor()

    cursor.execute(sql)
    messages = cursor.fetchall()
    print(len(messages))
    for count, message in enumerate(messages):
        msg_date_flat = remove_non_ascii(message[1].replace('\\r', ''))
        console.print(
            f"Processing message {count} - {msg_date_flat}",
            style=info_style,
        )
        from_hash = hashlib.sha256(message[1].encode("utf-8")).hexdigest()
        sql = "SELECT 1 FROM email_facts WHERE fact_hash = ? LIMIT 1"
        cursor.execute(sql, (from_hash,))
        row_exists = cursor.fetchone() is not None
        if not row_exists:
            # print(message)
            payload = remove_blank_lines(message[7])
            # Square brackets cause problems with rich printing
            payload = payload.replace("[", "(").replace("]", ")")
            msg_date = parser.parse(message[2])
            sender = message[3]
            receiver = message[4]
            subject = message[5]
            if payload.isspace():
                console.print("There is no message in the email.", style=error_style)
                continue
            console.print(f"Creating fact(s) related to {config.your_name}.", style=info_style)
            start_time = time.perf_counter()
            facts = do_facts(
                message=payload,
                msg_date=msg_date,
                subject=subject,
                sender=sender,
                receiver=receiver,
            )
            # print(facts)
            end_time = time.perf_counter()
            elapsed_time = round((end_time - start_time), 3)

            console.print(f"Time spent find facts: {elapsed_time}", style=info_style)

            try:
                start = facts.index("{")
                end = facts.rindex("}") + 1
                json_str = facts[start:end]
                # loads and dumps to flatten the json, really...
                checked_json = json.dumps(json.loads(json_str))

            except (ValueError, json.JSONDecodeError) as e:
                console.print(f"Error extracting JSON: {e}", style=error_style)
                # Just to bang something into the spot, so that it's skipped next iteration of this script.
                checked_json="{}"

            console.print(f"Writing fact: {checked_json}", style=success_style)
            write_msg_to_db(
                fact_hash=f"{from_hash}",
                fact_date=message[1],
                msg_from=message[0],
                facts=checked_json,
                table_name="email_facts",
                connection=connection,
            )

            console.print("─" * 40, style=line_style)
