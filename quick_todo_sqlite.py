"""Quick TODO Manager backed by a local SQLite database file."""

import csv
import os
from datetime import date, datetime
import sqlite3


def connect_database():
    connection = sqlite3.connect("todos.db")
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            planned_date TEXT NULL,
            comment TEXT NULL,
            long_comment_file TEXT NULL,
            completed TEXT NULL,
            category TEXT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            archived INTEGER DEFAULT 0
        )
        """
    )
    connection.commit()
    return connection, cursor


def deadline_status(planned, completed, short=True):
    today = date.today()
    if planned and isinstance(planned, str):
        planned = date.fromisoformat(planned)
    if completed and isinstance(completed, str):
        completed = datetime.fromisoformat(completed)
    if completed:
        return "Completed" if short else f"Completed at {completed.date()}"
    if not planned:
        return "No Deadline"
    if planned < today:
        return "Overdue"
    if planned == today:
        return "Due today"
    return f"{(planned - today).days} days left"


def display_todos(title, rows):
    print(f"\n--- {title} ---")
    print(f"Displaying {len(rows)} TODOs")
    print(f"{'ID':<5}{'Name':<24}{'Planned':<14}{'Category':<16}{'Status':<22}Comment")
    print("-" * 100)
    for row in rows:
        # Column order follows the table definition above.
        todo_id, name, planned, comment, _long_file, completed, category, created, archived = row
        status = deadline_status(planned, completed)
        archived_text = " [Archived]" if archived else ""
        print(
            f"{todo_id:<5}{name[:23]:<24}{str(planned or ''):<14}"
            f"{str(category or '')[:15]:<16}{status + archived_text:<22}"
            f"{comment or ''}"
        )
    print()


def add_todo(cursor, connection):
    name = input("TODO name: ").strip()
    if not name:
        print("Name cannot be blank.")
        return
    planned = input("Planned date (YYYY-MM-DD, optional): ").strip() or None
    comment = input("Short comment (optional): ").strip() or None
    long_comment = input("Long comment (optional): ").strip()
    category = input("Category (optional): ").strip() or None
    file_name = None
    if long_comment:
        safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
        file_name = f"todo_{safe_name}_{datetime.now():%Y%m%d%H%M%S}.txt"
        with open(file_name, "w", encoding="utf-8") as file:
            file.write(long_comment)
    cursor.execute(
        "INSERT INTO todos (name, planned_date, comment, long_comment_file, category) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, planned, comment, file_name, category),
    )
    connection.commit()
    print("TODO added.")


def fetch_one(cursor, todo_id):
    cursor.execute("SELECT * FROM todos WHERE id=?", (todo_id,))
    return cursor.fetchone()


def archive_todo(cursor, connection, todo_id=None, skip_confirmation=False):
    todo_id = todo_id or input("TODO ID to archive: ").strip()
    row = fetch_one(cursor, todo_id)
    if not row:
        print("TODO not found.")
        return
    if row[8]:
        print("TODO is already archived.")
        return
    if not skip_confirmation:
        display_todos("TODO to archive", [row])
        if input("Archive it? (y/n): ").lower() != "y":
            print("Cancelled.")
            return
    cursor.execute("UPDATE todos SET archived=TRUE WHERE id=?", (todo_id,))
    connection.commit()
    print("TODO archived.")


def restore_todo(cursor, connection):
    todo_id = input("TODO ID to restore: ").strip()
    row = fetch_one(cursor, todo_id)
    if not row:
        print("TODO not found.")
        return
    if not row[8]:
        print("TODO is not archived.")
        return
    if input("Restore it? (y/n): ").lower() == "y":
        cursor.execute("UPDATE todos SET archived=FALSE WHERE id=?", (todo_id,))
        connection.commit()
        print("TODO restored.")


def delete_todo(cursor, connection, todo_id=None):
    todo_id = todo_id or input("TODO ID to delete: ").strip()
    row = fetch_one(cursor, todo_id)
    if not row:
        print("TODO not found.")
        return
    display_todos("TODO to delete", [row])
    if not row[8]:
        print("This TODO is active. Choose archive first, or confirm permanent deletion.")
        print("1. Archive   2. Permanently delete   3. Cancel")
        choice = input("Choice: ").strip()
        if choice == "1":
            archive_todo(cursor, connection, todo_id, skip_confirmation=True)
            return
        if choice != "2":
            print("Cancelled.")
            return
    if input("Permanently delete? (y/n): ").lower() != "y":
        print("Cancelled.")
        return
    cursor.execute("DELETE FROM todos WHERE id=?", (todo_id,))
    connection.commit()
    if row[4] and os.path.exists(row[4]):
        os.remove(row[4])
    print("TODO deleted.")


def mark_completed(cursor, connection, todo_id=None):
    todo_id = todo_id or input("TODO ID to mark complete: ").strip()
    now = datetime.now().replace(microsecond=0).isoformat(sep=" ")
    cursor.execute("UPDATE todos SET completed=? WHERE id=?", (now, todo_id))
    if cursor.rowcount == 0:
        print("TODO not found.")
    else:
        connection.commit()
        print(f"Marked completed at {now}.")


def search_todos(cursor):
    print("Search by: 1) ID  2) exact name  3) title/comment text")
    choice = input("Choice: ").strip()
    if choice == "1":
        cursor.execute("SELECT * FROM todos WHERE id=?", (input("ID: ").strip(),))
    elif choice == "2":
        cursor.execute("SELECT * FROM todos WHERE name=?", (input("Name: ").strip(),))
    elif choice == "3":
        term = f"%{input('Search text: ').strip()}%"
        cursor.execute("SELECT * FROM todos WHERE name LIKE ? OR comment LIKE ?", (term, term))
    else:
        print("Invalid choice.")
        return
    rows = cursor.fetchall()
    display_todos("Search results", rows) if rows else print("No TODOs found.")


def print_long_comment(cursor):
    todo_id = input("TODO ID: ").strip()
    cursor.execute("SELECT long_comment_file FROM todos WHERE id=?", (todo_id,))
    row = cursor.fetchone()
    if row and row[0] and os.path.exists(row[0]):
        with open(row[0], encoding="utf-8") as file:
            print(file.read())
    else:
        print("No long comment found for that TODO.")


def filters_menu(cursor):
    print("1) Due date ascending  2) Due date descending  3) Completed")
    print("4) Incomplete  5) Category  6) Date range  7) Combined filters")
    choice = input("Choice: ").strip()
    if choice == "1":
        cursor.execute("SELECT * FROM todos ORDER BY planned_date ASC")
    elif choice == "2":
        cursor.execute("SELECT * FROM todos ORDER BY planned_date DESC")
    elif choice == "3":
        cursor.execute("SELECT * FROM todos WHERE completed IS NOT NULL")
    elif choice == "4":
        cursor.execute("SELECT * FROM todos WHERE completed IS NULL")
    elif choice == "5":
        cursor.execute("SELECT * FROM todos WHERE category=?", (input("Category: ").strip(),))
    elif choice == "6":
        start = input("Start date (YYYY-MM-DD): ").strip()
        end = input("End date (YYYY-MM-DD): ").strip()
        cursor.execute("SELECT * FROM todos WHERE planned_date BETWEEN ? AND ?", (start, end))
    elif choice == "7":
        query = "SELECT * FROM todos WHERE 1=1"
        values = []
        category = input("Category (blank for any): ").strip()
        completed = input("Completed? yes/no/blank: ").strip().lower()
        start = input("Start date (blank for any): ").strip()
        end = input("End date (blank for any): ").strip()
        if category:
            query += " AND category=?"
            values.append(category)
        if completed == "yes":
            query += " AND completed IS NOT NULL"
        elif completed == "no":
            query += " AND completed IS NULL"
        if start:
            query += " AND planned_date >= ?"
            values.append(start)
        if end:
            query += " AND planned_date <= ?"
            values.append(end)
        cursor.execute(query, tuple(values))
    else:
        print("Invalid choice.")
        return
    display_todos("Filtered TODOs", cursor.fetchall())


def show_deadline_status(cursor):
    cursor.execute("SELECT id, name, planned_date, completed, archived FROM todos")
    for todo_id, name, planned, completed, archived in cursor.fetchall():
        status = deadline_status(planned, completed, short=False)
        suffix = " - Archived" if archived else ""
        print(f"{todo_id}. {name} - {status}{suffix}")


def export_to_csv(cursor):
    cursor.execute("SELECT * FROM todos")
    rows = cursor.fetchall()
    if not rows:
        print("No TODOs to export.")
        return
    filename = f"todos_export_{datetime.now():%Y%m%d%H%M%S}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["ID", "Name", "Planned Date", "Comment", "Long Comment File",
                         "Completed", "Category", "Created At", "Archived"])
        writer.writerows(rows)
    print(f"Exported to {filename}.")


def select_todo(cursor, connection):
    todo_id = input("TODO ID: ").strip()
    row = fetch_one(cursor, todo_id)
    if not row:
        print("TODO not found.")
        return
    while True:
        display_todos("Selected TODO", [row])
        print("1) Toggle archive  2) Delete  3) Mark complete  4) Mark incomplete  5) Back")
        choice = input("Choice: ").strip()
        if choice == "1":
            cursor.execute("UPDATE todos SET archived=NOT archived WHERE id=?", (todo_id,))
            connection.commit()
        elif choice == "2":
            delete_todo(cursor, connection, todo_id)
            return
        elif choice == "3":
            mark_completed(cursor, connection, todo_id)
        elif choice == "4":
            cursor.execute("UPDATE todos SET completed=NULL WHERE id=?", (todo_id,))
            connection.commit()
            print("Marked incomplete.")
        elif choice == "5":
            return
        else:
            print("Invalid choice.")
        row = fetch_one(cursor, todo_id)
        if not row:
            return


def main():
    connection, cursor = connect_database()
    try:
        while True:
            print("\n--- QUICK TODO MANAGER ---")
            print("1 Add  2 Delete  3 Archive  4 Mark complete  5 Search")
            print("6 Select TODO  7 Show long comment  8 Filters  9 Deadline status")
            print("10 Show all  11 Restore  12 Export CSV  13 Exit")
            choice = input("Choice: ").strip()
            if choice == "1":
                add_todo(cursor, connection)
            elif choice == "2":
                delete_todo(cursor, connection)
            elif choice == "3":
                archive_todo(cursor, connection)
            elif choice == "4":
                mark_completed(cursor, connection)
            elif choice == "5":
                search_todos(cursor)
            elif choice == "6":
                select_todo(cursor, connection)
            elif choice == "7":
                print_long_comment(cursor)
            elif choice == "8":
                filters_menu(cursor)
            elif choice == "9":
                show_deadline_status(cursor)
            elif choice == "10":
                cursor.execute("SELECT * FROM todos WHERE archived=FALSE")
                display_todos("Active TODOs", cursor.fetchall())
                cursor.execute("SELECT * FROM todos WHERE archived=TRUE")
                display_todos("Archived TODOs", cursor.fetchall())
            elif choice == "11":
                restore_todo(cursor, connection)
            elif choice == "12":
                export_to_csv(cursor)
            elif choice == "13":
                break
            else:
                print("Invalid choice. Try again.")
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    main()
