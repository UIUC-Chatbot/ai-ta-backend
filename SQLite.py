import json
import sqlite3
from ai_ta_backend.utils.types import DocumentMetadata

def insert_doc(doc: DocumentMetadata, commit_on_change: bool = True):
  # Establishing the connection
  db = sqlite3.connect('science.db')
  cursor = db.cursor()
  try:
    # Dynamically get field names from DocumentMetadata
    fields = list(DocumentMetadata.schema()["properties"].keys())
    # Convert field names to the format expected in the SQL statement
    sql_fields = ", ".join(fields)
    sql_values = ", ".join(["?"] * len(fields))  # SQLite uses "?" as placeholder

    add_document = f"INSERT INTO documents ({sql_fields}) VALUES ({sql_values})"

    # Convert DocumentMetadata object to a tuple for database insertion
    # No lists in SQLite: if type == list, do json.dumps()
    data_document = tuple(
      json.dumps(getattr(doc, field)) if isinstance(getattr(doc, field), list) else getattr(doc, field)
      for field in fields
    )

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