import json
import sqlite3

from ai_ta_backend.utils.types import DocumentMetadata

DB_NAME = "science.db"
TABLE_NAME = "documents"


def insert_doc(doc: DocumentMetadata, commit_on_change: bool = True):
  db = sqlite3.connect(DB_NAME)
  cursor = db.cursor()
  try:
    create_database_and_table(cursor)

    # Dynamically get field names from DocumentMetadata
    # ! TODO: have to handle this better. For section titles, need to keep that separate. Adjust in "create_table_if_missing" function.

    fields = list(DocumentMetadata.schema()["properties"].keys())
    for field in fields:
      if field == "additional_fields":
        print("DocumentMetadata['additional_fields']", doc.additional_fields)
        for key in doc.additional_fields.keys():
          add_column_if_missing(db, TABLE_NAME, key, "TEXT")
      else:
        add_column_if_missing(db, TABLE_NAME, field, "TEXT")

    # Convert field names to the format expected in the SQL statement
    sql_fields = ", ".join(fields)
    sql_values = ", ".join(["?"] * len(fields))  # SQLite uses "?" as placeholder

    add_document = f"INSERT INTO {TABLE_NAME} ({sql_fields}) VALUES ({sql_values})"

    # Convert DocumentMetadata object to a tuple for database insertion
    # No lists in SQLite: if type == list, do json.dumps()
    data_document = tuple(
        json.dumps(getattr(doc, field)) if isinstance(getattr(doc, field), list) else getattr(doc, field)
        for field in fields)

    cursor.execute(add_document, data_document)

    if commit_on_change:
      db.commit()
      print("✅ Document committed to DB.")
    else:
      print("⏱️ Document queued successfully.")

  except sqlite3.Error as err:
    print(f"Error in SQL upload: {err}")
  finally:
    cursor.close()
    db.close()
    print("SQLite connection is closed")


def create_database_and_table(cursor):
  """
  Create database and table if not exists.
  """
  # Todo make this dynamic from the DocumentMetadata schema
  cursor.execute('''
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        authors TEXT,
        journal_name TEXT,
        publication_date DATE,
        keywords TEXT,
        doi TEXT,
        title TEXT,
        subtitle TEXT,
        visible_urls TEXT,
        field_of_science TEXT,
        concise_summary TEXT,
        specific_questions_document_can_answer TEXT
    );
    ''')


def add_column_if_missing(db, table_name, column_name, data_type):
  """
  Add column to table if not exists.
  """
  cursor = db.cursor()
  cursor.execute(f"PRAGMA table_info({table_name});")
  columns = [info[1] for info in cursor.fetchall()]  # Column names are in the second position
  if column_name not in columns:
    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {data_type}")
    print(f"Column {column_name} added to {table_name}.")
  cursor.close()


# !Manual method (auto-method used below)
# SQL command to insert the data
# add_document = (
#   "INSERT INTO documents "
#   "(authors, journal_name, publication_date, keywords, doi, title, subtitle, visible_urls, field_of_science, concise_summary, questions_document_can_answer) "
#   "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
# )

# Convert DocumentMetadata object to a tuple for database insertion
# data_document = (
#   json.dumps(doc.authors),  # Convert list to string
#   doc.journal_name,
#   doc.publication_date,
#   json.dumps(doc.keywords),  # Convert list to string
#   doc.doi,
#   doc.title,
#   doc.subtitle,
#   json.dumps(doc.visible_urls),  # Convert list to string
#   doc.field_of_science,
#   doc.concise_summary,
#   json.dumps(doc.specific_questions_document_can_answer)  # Convert list to string
# )
