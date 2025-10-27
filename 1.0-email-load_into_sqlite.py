#!/usr/bin/env python3
"""
What it does:

This script removes all attachments from a mailbox file (.mbox)
and writes the resulting plain text content to a new output file.
The original message headers, including sender information, /e preserved.

In essence, this script is a simple mailbox filter that extracts
and preserves only the textual parts of emails in a mailbox file,
discarding any attachments.

Inputs:

    A .mbox file to process (input_file)
    A desired output file name (output_file)

Outputs:

    A new .mbox file with only the plain text content of the input messages
"""

import argparse
import errno
import mailbox
import os
import sys
import sqlite3
import base64
import re
import datetime

from bs4 import BeautifulSoup
from dateutil import parser

from rich import print
from rich.console import Console
from rich.style import Style

import config
from utilities import remove_non_ascii, parse_people2, remove_null_chars, table_exists


def extract_text_from_message(
    original_message: mailbox.mboxMessage,
) -> mailbox.mboxMessage:
    """
    Extracts only the plain text content from a mailbox message object, removing attachments.

    Args:
        original_message (mailbox.Message): The mailbox message object to process.

    Returns:
        mailbox.Message: A new message object containing only the plain text content.
    """

    # Create a new message object to store the text content
    new_message = mailbox.mboxMessage()

    # Copy headers from the original message to the new message
    for header, value in original_message.items():
        new_message[header] = value
    new_message.set_from(original_message.get_from())
    # Extract text parts and append them to the new message
    text_parts = []
    for part in original_message.walk():
        if part.get_content_type() == "text/plain":
            # Decode the payload and remove non-ascii characters
            decoded_payload = part.get_payload(decode=True).decode(
                "utf-8", errors="replace"
            )
            cleaned_payload = remove_null_chars(remove_non_ascii(decoded_payload))
            text_parts.append(cleaned_payload)

    # Set the payload of the new message to the combined text parts
    new_message.set_payload("\n".join(text_parts))

    return new_message


def create_tables():
    connection = sqlite3.connect(config.sqlite_email_file)
    cursor = connection.cursor()
    sql = "CREATE TABLE msgs (id INTEGER PRIMARY KEY AUTOINCREMENT, from_line TEXT UNIQUE, msg_date TIMESTAMP, sender TEXT, receiver TEXT, subject TEXT, headers TEXT, payload TEXT)"
    cursor.execute(sql)
    sql = "CREATE TABLE raw_msgs (id INTEGER PRIMARY KEY AUTOINCREMENT, from_line TEXT UNIQUE, msg_date TIMESTAMP, sender TEXT, receiver TEXT, subject TEXT, headers TEXT, payload TEXT)"
    cursor.execute(sql)
    sql = "CREATE INDEX index_msg_from ON msgs (from_line);"
    cursor.execute(sql)
    sql = "CREATE INDEX index_raw_msgs_from ON raw_msgs (from_line);"
    cursor.execute(sql)
    sql = "CREATE INDEX index_sender ON raw_msgs (sender);"
    cursor.execute(sql)
    sql = "CREATE TABLE address_book (id INTEGER PRIMARY KEY AUTOINCREMENT, email_addr TEXT UNIQUE, display_name TEXT)"
    cursor.execute(sql)
    sql = "CREATE INDEX index_address ON address_book (email_addr);"
    cursor.execute(sql)
    connection.close()


def write_msg_to_db(
    from_header: str,
    msg_date: datetime,
    sender: str,
    receiver: str,
    subject: str,
    headers: str,
    payload: str,
    table_name: str,
    connection: sqlite3.Connection,
) -> bool:
    cursor = connection.cursor()
    stripped_payload = payload.replace("\n", "").replace("\r", "").replace('"', "'")
    if subject is not None:
        stripped_subject = (
            str(subject).replace("\n", "").replace("\r", "").replace('"', "'")
        )
    else:
        stripped_subject = ["None"]
    sql = f'INSERT INTO {table_name} (from_line, msg_date, sender, receiver, subject, headers, payload) VALUES  ("{from_header}", "{msg_date}", "{sender}", "{receiver}", "{stripped_subject}", "{headers}", "{stripped_payload}")'
    # print(sql)
    try:
        cursor.execute(sql)
    except sqlite3.IntegrityError as e:
        if (
            hasattr(e, "sqlite_errorname")
            and "SQLITE_CONSTRAINT_UNIQUE" in e.sqlite_errorname
        ):
            print(f"Record already exists. {e}")
            # print(sql)
        else:
            print(e)
    connection.commit()
    cursor.close()


def add_recipient(
    receiver_addr: str, receiver_name: str, recipients_list: dict
) -> dict:
    # print(f"Recipient List: {recipients_list}")
    if receiver_addr not in recipients_list:
        recipients_list[receiver_addr] = receiver_name
    else:
        # Trying to catch a name if possible...
        if not recipients_list[receiver_addr]:
            recipients_list[receiver_addr] = receiver_name
        elif len(receiver_name) > len(recipients_list[receiver_addr]):
            recipients_list[receiver_addr] = receiver_name
    # print(f"Recipient List: {recipients_list}")
    return recipients_list


def parse_headers(headers: list) -> list:
    if headers is not None:
        stripped_headers = []
        for k, v in headers:
            stripped_headers.append(
                (f"{k}:{v},").replace("\n", "").replace("\r", "").replace('"', "'")
            )
            return stripped_headers
    else:
        return ["None"]


def strip_html(message_payload):
    soup = BeautifulSoup(message_payload, "html.parser", from_encoding="utf-8")
    return soup.text


def clean_up_msg(message=False):
    lines = message.get_payload().split("\n")
    cleaned_lines = []

    for line in lines:
        flag = False
        if re.match(r".*--.*Original Message.*--.*", line):
            print('Removign "Original Message"')
            flag = True
            break
        if re.match(r"On.*wrote:", line):
            print('Removing "On...wrote:"')
            flag = True
            break
        if re.match(r".*--.*Forwarded Message.*--.*", line):
            print('Removing "Forward Message"')
            flag = True
            break
        if line.startswith("--"):
            print("Removing sig")
            flag = True
            break  # Exit the loop when "-- " is found
        if line.startswith("m!"):
            print("Removing m!")
            flag = True
            break
        if re.match(r"^ttul,$", line):
            print('Removing "ttul"')
            flag = True
            break
        if line.startswith("k;"):
            print("Removing k;")
            flag = True
            break
        if re.match(r"^Cheers$", line):
            print('Removing "ttul"')
            flag = True
            break
        cleaned_lines.append(line)

    cleaned_string = "\n".join(cleaned_lines)

    message.set_payload(cleaned_string)

    return message, flag


def parse_date_from_from_header(text):
    # Regular expression to match the date format in the strings
    # Matches patterns like "Mon May 09 10:06:02 +0000 2022" or "Sat Dec  6 13:41:10 2003"
    # date_pattern = re.compile(r'\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2} \d{2}:\d{2}:\d{2} [+-]\d{4} \d{4}|\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2} \d{2}:\d{2}:\d{2} \d{4}')
    date_pattern = re.compile(
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}(?:\s+[+-]\d{4})?\s+\d{4}"
    )
    # Search for the date pattern in the input text
    match = date_pattern.search(text)

    if match:
        date_str = match.group()
        try:
            # Parse the date string using dateutil.parser
            date_obj = parser.parse(date_str)
            return date_obj
        except ValueError as e:
            print(f"Error parsing date: {e}")
            sys.exit(1)
    else:
        print("No date found in the string.")
        sys.exit(1)


def update_email_record(
    table_name: str,
    column: str,
    payload: str,
    row_id: int,
    connection: sqlite3.Connection,
) -> bool:
    cursor2 = connection.cursor()
    sql2 = f"UPDATE {table_name} SET {column} = ? WHERE id = ?;"
    # print(sql2)
    try:
        cursor2.execute(sql2, (payload, row_id))
    except sqlite3.IntegrityError as e:
        if (
            hasattr(e, "sqlite_errorname")
            and "SQLITE_CONSTRAINT_UNIQUE" in e.sqlite_errorname
        ):
            print(f"Record already exists. {e}")
            # print(sql2)
        else:
            print(e)
    connection.commit()
    cursor2.close()

def add_address(
        email_addr: str,
        display_name: str,
        table_name: str,
        connection: sqlite3.Connection,
    ):

    #Email is so dirty
    email_addr = email_addr.replace('"', "").replace("'","")
    display_name = display_name.replace('"', "").replace("'","")
    
    #Don't add emails with no display name or the display name is the email address.
    if display_name and email_addr not in display_name:
        sql = f"SELECT * FROM {table_name} WHERE email_addr LIKE '%{email_addr}%'"
        # print(sql)
        cursor = connection.cursor()
        cursor.execute(sql)
        result = cursor.fetchone()
        #If there is a record and diplay_name recorded isn't smaller
        if result and not len(result[2]) < len(display_name):
            # console.print(f"Record for {email_addr} exists.")
            return(False)

        # #If the display name is bigger use the bigger one.
        # elif result and len(result[2]) < len(display_name):
        #     print(result)
        #     update_email_record(table_name=table_name,
        #                         column="display_name" ,
        #                         payload=display_name,
        #                         row_id=result[0],
        #                         connection=connection)
        else:
            sql = f'INSERT INTO {table_name} (email_addr, display_name) VALUES  ("{email_addr}", "{display_name}")'

            try:
                cursor.execute(sql)
            except sqlite3.IntegrityError as e:
                if (
                    hasattr(e, "sqlite_errorname")
                    and "SQLITE_CONSTRAINT_UNIQUE" in e.sqlite_errorname
                ):
                    print(f"Record already exists. {e}")
                    # print(sql)
                else:
                    print(e)
        connection.commit()
        cursor.close()

    return(True)


if __name__ == "__main__":
    DB_NAME1 = "msgs"
    DB_NAME2 = "raw_msgs"
    arg_parser = argparse.ArgumentParser(
        description="Loads a mbox file into a sqlite DB"
    )
    arg_parser.add_argument("input_file", help="Specify the file to be processed")
    args = arg_parser.parse_args()

    console = Console()
    console.clear()
    # If the file doesn't exist stop.
    if not args.input_file or not os.path.isfile(args.input_file):
        console.print("Missing argument")
        console.print(arg_parser.format_help())
        sys.exit(errno.EINVAL)

    mbox = mailbox.mbox(args.input_file)
    console.print("Opening mbox {}.".format(args.input_file))

    if not os.path.isfile(config.sqlite_email_file):
        create_tables()

    connection = sqlite3.connect(config.sqlite_email_file)
    if not table_exists(connection=connection, table_name=DB_NAME1):
        create_tables()

    recipients_list = {}

    # First pass to remove attachments
    for count, original_message in enumerate(mbox):
        console.print(
            "Processing message {} - {}.".format(
                count, remove_non_ascii(original_message.get_from().replace("\r", ""))
            )
        )

        # Bail out before parsing anything.
        # Add your exceptions here, for problematic messages...
        if "X-Gmail-Labels" in original_message and (
            "Chat" in original_message["X-Gmail-Labels"]
            or "Spam" in original_message["X-Gmail-Labels"]
            or (
                original_message["subject"] is not None
                and "SQL dump -" in str(original_message["subject"])
            )
        ):
            continue

        # Bail on shit messages
        if not original_message.get("to", "") or not original_message.get("from", ""):
            continue

        sender, receiver = parse_people2(message=original_message)
        sender_name, sender_addr = sender[0]

        receiver_name, receiver_addr = receiver[0]

        # # I don't think emails to me an many others give insight into me...?
        if (
            len(receiver) > 1 or "Junk" in receiver_name
        ) and sender_addr.lower() not in config.emails_dict:
            continue

        # I don't think emails to me an many others give insight into me...?
        if "Junk" in sender_name and receiver_addr.lower() not in config.emails_dict:
            continue



        new_message = extract_text_from_message(original_message=original_message)

        # Decode the message to ascii
        if isinstance(new_message.get_payload(), list):
            for item in new_message.get_payload():
                if item["Content-Type"].startswith(("text/html", "text/plain")):
                    if "base64" in item["Content-Transfer-Encoding"]:
                        decoded_bytes = base64.b64decode(item.get_payload())
                        new_message.set_payload(payload=decoded_bytes)
                    else:
                        new_message.set_payload(payload=item.get_payload())

        clean_payload = remove_non_ascii(new_message.get_payload())
        clean_payload = strip_html(message_payload=clean_payload)
        # This is some janky smashing to ascii. I'm too annoyed with email to investigate.
        new_message.set_payload(payload=clean_payload.encode("ascii", "ignore"))

        # This loops until there are no more "hits" on sigs/replies
        flag = True
        while flag:
            new_message, flag = clean_up_msg(message=new_message)

        # Write all messages to the raw_msgs table for later recipient parsing.
        write_msg_to_db(
            from_header=original_message.get_from(),
            msg_date=parse_date_from_from_header(original_message.get_from()),
            sender=sender_addr,
            receiver=receiver_addr,
            subject=new_message["subject"],
            headers=parse_headers(new_message._headers),
            payload=new_message.get_payload(),
            table_name=DB_NAME2,
            connection=connection,
        )

        if sender_addr.lower() in config.emails_dict:
            if config.emails_dict[sender_addr.lower()] == config.your_name:
                write_msg_to_db(
                    from_header=original_message.get_from(),
                    msg_date=parse_date_from_from_header(original_message.get_from()),
                    sender=sender_addr,
                    receiver=receiver_addr,
                    subject=new_message["subject"],
                    headers=parse_headers(new_message._headers),
                    payload=new_message.get_payload(),
                    table_name=DB_NAME1,
                    connection=connection,
                )
            # Add the email to the list of people I've sent mail to
            recipients_list = add_recipient(
                receiver_addr=receiver_addr,
                receiver_name=receiver_name,
                recipients_list=recipients_list,
            )
            # Some hacky stuff because I'm to tired to properly figure out the second pass sender info
            add_address(email_addr=sender_addr,
                        display_name=sender_name,
                        table_name="address_book",
                        connection=connection)
            add_address(email_addr=receiver_addr,
                        display_name=receiver_name,
                        table_name="address_book",
                        connection=connection)
    # Second pass
    # Ensures that only people the recipients_list are added to the DB_NAME1 db
    for recipient, value in recipients_list.items():
        sql = f"SELECT * FROM {DB_NAME2} WHERE sender LIKE '%{recipient}%'"
        cursor = connection.cursor()
        console.print(f"Checking messages from {recipient}")
        for msg in cursor.execute(sql):
            # skip msg[0] as it's 'id' col
            write_msg_to_db(
                from_header=msg[1],
                msg_date=msg[2],
                sender=msg[3],
                receiver=msg[4],
                subject=msg[5],
                headers=msg[6],
                payload=msg[7],
                table_name=DB_NAME1,
                connection=connection,
            )

