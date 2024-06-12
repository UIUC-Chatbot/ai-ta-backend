import os
import sqlite3
from embedding import get_embeddings
from typing import Dict, List
import json

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
                ULD INTEGER PRIMARY KEY AUTOINCREMENT,
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
                ULD INTEGER PRIMARY KEY AUTOINCREMENT,
                num_tokens INTEGER,
                Section_Title TEXT,
                Section_Num TEXT
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS article_sections (
                Article_ID INTEGER,
                Section_ID INTEGER,
                PRIMARY KEY (Article_ID, Section_ID),
                FOREIGN KEY (Article_ID) REFERENCES articles(ULD),
                FOREIGN KEY (Section_ID) REFERENCES sections(ULD)
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS contexts (
                ULD INTEGER PRIMARY KEY AUTOINCREMENT,
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
                Section_ID INTEGER,
                Context_ID INTEGER,
                PRIMARY KEY (Section_ID, Context_ID),
                FOREIGN KEY (Section_ID) REFERENCES sections(ULD),
                FOREIGN KEY (Context_ID) REFERENCES contexts(ULD)
            )
        ''')

        conn.commit()
        conn.close()

        print("Database and tables created successfully.")
    else:
        print("Database already exists. No changes made.")


def insert_data(metadata: Dict, total_tokens: int, grouped_data: List[Dict], db_path: str = 'articles.db'):
    """
    Inserts article metadata and sections into the database.

    :param metadata: Dictionary containing article metadata (title, date_published, journal, authors).
    :param total_tokens: Total number of tokens in the article.
    :param grouped_data: List of dictionaries containing section data (tokens, sec_num, sec_title).
    :param db_path: Path to the SQLite database file.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute('''
        INSERT INTO articles (Title, Date_published, Journal, Authors, Num_tokens, Sections)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        metadata['title'],
        metadata['date_published'],
        metadata['journal'],
        ', '.join(metadata['authors']),
        total_tokens,
        ', '.join([section['sec_num'] for section in grouped_data])
    ))

    article_id = cur.lastrowid
    for section in grouped_data:
        cur.execute('''
            INSERT INTO sections (num_tokens, Section_Num, Section_Title)
            VALUES (?, ?, ?)
        ''', (section["tokens"], section["sec_num"], section["sec_title"]))
        section_id = cur.lastrowid

        if section["tokens"] > 7000:
            for text, token in zip(section["chunk_text"], section["chunk_tokens"]):
                cur.execute('''
                    INSERT INTO contexts (text, Section_Num, Section_Title, num_tokens, `Embedding_nomic_1.5`, stop_reason)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (text, section["sec_num"], section["sec_title"], token, section["embedding"], "Token limit"))
                context_id = cur.lastrowid

                cur.execute('''
                    INSERT INTO sections_contexts (Section_ID, Context_ID)
                    VALUES (?, ?)
                ''', (section_id, context_id))

        else: 
            cur.execute('''
                INSERT INTO contexts (text, Section_Num, Section_Title, num_tokens, `Embedding_nomic_1.5`, stop_reason)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (section["text"], section["sec_num"], section["sec_title"], section["tokens"], section["embedding"], "Section"))
            context_id = cur.lastrowid
            cur.execute('''
                        INSERT INTO sections_contexts (Section_ID, Context_ID)
                        VALUES (?, ?)
                    ''', (section_id, context_id))

        cur.execute('''
            INSERT INTO article_sections (Article_ID, Section_ID)
            VALUES (?, ?)
        ''', (article_id, section_id))

    conn.commit()
    conn.close()

    print("Metadata and sections inserted successfully.")


# db_path = 'articles.db'
# initialize_database(db_path)

# insert_data(metadata, total_tokens, grouped_data, db_path)