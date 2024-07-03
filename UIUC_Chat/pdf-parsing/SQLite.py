import json
import os
import sqlite3
from typing import Dict, List, Optional

import fastnanoid # type: ignore


def initialize_database(db_path):
  """
    Initializes the database and creates the necessary tables if they don't already exist.

    :param db_path: Path to the SQLite database file.
    """
  if not os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                ID TEXT PRIMARY KEY,
                Num_tokens INTEGER,
                Title TEXT,
                Date_published TEXT,
                Journal TEXT,
                Authors TEXT,
                Sections TEXT
            )
        ''')

    cur.execute('''
            CREATE TABLE IF NOT EXISTS sections (
                ID TEXT PRIMARY KEY,
                num_tokens INTEGER,
                Section_Title TEXT,
                Section_Num TEXT
            )
        ''')

    cur.execute('''
            CREATE TABLE IF NOT EXISTS article_sections (
                Article_ID TEXT,
                Section_ID TEXT,
                PRIMARY KEY (Article_ID, Section_ID),
                FOREIGN KEY (Article_ID) REFERENCES articles(ID),
                FOREIGN KEY (Section_ID) REFERENCES sections(ID)
            )
        ''')

    cur.execute('''
            CREATE TABLE IF NOT EXISTS contexts (
                ID TEXT PRIMARY KEY,
                text TEXT,
                Section_Title TEXT,
                Section_Num TEXT,
                num_tokens INTEGER,
                Page INTEGER,
                `Embedding_nomic_1.5` TEXT,
                Stop_Reason TEXT
            )
        ''')

    cur.execute('''
            CREATE TABLE IF NOT EXISTS sections_contexts (
                Section_ID TEXT,
                Context_ID TEXT,
                PRIMARY KEY (Section_ID, Context_ID),
                FOREIGN KEY (Section_ID) REFERENCES sections(ID),
                FOREIGN KEY (Context_ID) REFERENCES contexts(ID)
            )
        ''')

    conn.commit()
    conn.close()

    print("Database and tables created successfully.")
  else:
    print("Database already exists. No changes made.")


def insert_data(metadata: Dict,
                total_tokens: int,
                grouped_data: List[Dict],
                db_path: str,
                references: Optional[Dict] = None,
                ref_num_tokens: Optional[Dict] = None):
  """
    Inserts article metadata and sections into the database.

    :param metadata: Dictionary containing article metadata (title, date_published, journal, authors).
    :param total_tokens: Total number of tokens in the article.
    :param grouped_data: List of dictionaries containing section data (tokens, sec_num, sec_title).
    :param db_path: Path to the SQLite database file.
    """
  if references is None:
    references = {} 
  if ref_num_tokens is None:
    ref_num_tokens = {} 

  conn = sqlite3.connect(db_path)
  cur = conn.cursor()

  article_id = fastnanoid.generate()
  cur.execute(
      '''
        INSERT INTO articles (ID, Title, Date_published, Journal, Authors, Num_tokens, Sections)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (article_id, metadata['title'], metadata['date_published'], metadata['journal'], ', '.join(
          metadata['authors']), total_tokens, ', '.join([section['sec_num'] for section in grouped_data])))

  for key in references:
    ref_id = fastnanoid.generate()
    cur.execute(
        '''
            INSERT INTO sections (ID, num_tokens, Section_title, Section_Num)
            VALUES (?, ?, ?, ?)
        ''', (ref_id, ref_num_tokens[key], references[key], key))

    cur.execute(
        '''
                INSERT INTO article_sections (Article_ID, Section_ID)
                VALUES (?, ?)
            ''', (article_id, ref_id))

  for section in grouped_data:
    section_id = fastnanoid.generate()
    cur.execute(
        '''
            INSERT INTO sections (ID, num_tokens, Section_Num, Section_Title)
            VALUES (?, ?, ?, ?)
        ''', (section_id, section["tokens"], section["sec_num"], section["sec_title"]))

    if section["tokens"] > 7000:
      for text, token in zip(section["chunk_text"], section["chunk_tokens"]):
        context_id = fastnanoid.generate()
        cur.execute(
            '''
                    INSERT INTO contexts (ID, text, Section_Num, Section_Title, num_tokens, `Embedding_nomic_1.5`, stop_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
            (context_id, text, section["sec_num"], section["sec_title"], token, json.dumps(
                section["embedding"][0]), "Token limit"))

        cur.execute(
            '''
                    INSERT INTO sections_contexts (Section_ID, Context_ID)
                    VALUES (?, ?)
                ''', (section_id, context_id))

    else:
      context_id = fastnanoid.generate()
      cur.execute(
          '''
                INSERT INTO contexts (ID, text, Section_Num, Section_Title, num_tokens, `Embedding_nomic_1.5`, stop_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (context_id, section["text"], section["sec_num"], section["sec_title"], section["tokens"],
                  json.dumps(section["embedding"][0]), "Section"))
      cur.execute(
          '''
                        INSERT INTO sections_contexts (Section_ID, Context_ID)
                        VALUES (?, ?)
                    ''', (section_id, context_id))

    cur.execute(
        '''
            INSERT INTO article_sections (Article_ID, Section_ID)
            VALUES (?, ?)
        ''', (article_id, section_id))

  conn.commit()
  conn.close()
