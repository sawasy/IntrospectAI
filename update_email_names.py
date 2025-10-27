import sys
import sqlite3
import os

from rich import print
from rich.console import Console

import config

if __name__ == "__main__":
    DB_NAME1 = "msgs"
    DB_NAME2 = "raw_msgs"

    console = Console()
    console.clear()

    if not os.path.isfile(config.sqlite_email_file):
        sys.exit(1)

    connection = sqlite3.connect(config.sqlite_email_file)

    #Fix address book names
    for k,v  in config.emails_dict.items():
        find_sql = f"SELECT * FROM address_book WHERE email_addr LIKE '%{k}%'"
        cursor = connection.cursor()
        addr_results = cursor.execute(find_sql).fetchall()
        for addr_address in addr_results:
            addr_update_sql = "UPDATE address_book SET display_name = ? WHERE id = ?;"
            cursor2 = connection.cursor()
            try:
                cursor2.execute(addr_update_sql, (v, addr_address[0]))
            except sqlite3.IntegrityError as e:
                if (
                    hasattr(e, "sqlite_errorname")
                    and "SQLITE_CONSTRAINT_UNIQUE" in e.sqlite_errorname
                ):
                    print(f"Record already exists. {e}")
                else:
                    print(e)
            connection.commit()
            cursor2.close()

    console.print("Updating display names for email addresses in database")

    address_sql = sql = "SELECT * FROM address_book;"
    cursor = connection.cursor()
    for address in cursor.execute(sql):
        pretty_entry = f"{address[2]} <{address[1]}>"
        console.print(pretty_entry)

        for item in ["sender", "receiver"]:
            console.print(f"Doing {item}")
            find_sql = f"SELECT * FROM {DB_NAME1} WHERE {item} LIKE '%{address[1]}%'"
            print(find_sql)            
            cursor = connection.cursor()
            results = cursor.execute(find_sql).fetchall()
            console.print(f"{len(results)} records found.")
            for email_msg in results:
                sys.stdout.write("Updating record: %d  \r" % (email_msg[0]))
                sys.stdout.flush()
                cursor2 = connection.cursor()
                update_sql = f"UPDATE {DB_NAME1} SET {item} = ? WHERE id = ?;"
                try:
                    cursor2.execute(update_sql, (pretty_entry, email_msg[0]))
                except sqlite3.IntegrityError as e:
                    if (
                        hasattr(e, "sqlite_errorname")
                        and "SQLITE_CONSTRAINT_UNIQUE" in e.sqlite_errorname
                    ):
                        print(f"Record already exists. {e}")
                    else:
                        print(e)
                connection.commit()
                cursor2.close()

