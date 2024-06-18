import os
import sqlite3
from typing import Dict, List
import ulid
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
                ULID TEXT PRIMARY KEY,
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
                ULID TEXT PRIMARY KEY,
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
                FOREIGN KEY (Article_ID) REFERENCES articles(ULID),
                FOREIGN KEY (Section_ID) REFERENCES sections(ULID)
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS contexts (
                ULID TEXT PRIMARY KEY,
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
                FOREIGN KEY (Section_ID) REFERENCES sections(ULID),
                FOREIGN KEY (Context_ID) REFERENCES contexts(ULID)
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
    
    article_ulid = str(ulid.new())
    cur.execute('''
        INSERT INTO articles (ULID, Title, Date_published, Journal, Authors, Num_tokens, Sections)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        article_ulid,
        metadata['title'],
        metadata['date_published'],
        metadata['journal'],
        ', '.join(metadata['authors']),
        total_tokens,
        ', '.join([section['sec_num'] for section in grouped_data])
    ))

    for section in grouped_data:
        section_ulid = ulid.new().str
        cur.execute('''
            INSERT INTO sections (ULID, num_tokens, Section_Num, Section_Title)
            VALUES (?, ?, ?, ?)
        ''', (section_ulid, section["tokens"], section["sec_num"], section["sec_title"]))

        if section["tokens"] > 7000:
            for text, token in zip(section["chunk_text"], section["chunk_tokens"]):
                context_ulid = ulid.new().str
                cur.execute('''
                    INSERT INTO contexts (ULID, text, Section_Num, Section_Title, num_tokens, `Embedding_nomic_1.5`, stop_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (context_ulid, text, section["sec_num"], section["sec_title"], token, json.dumps(section["embedding"]), "Token limit"))

                cur.execute('''
                    INSERT INTO sections_contexts (Section_ID, Context_ID)
                    VALUES (?, ?)
                ''', (section_id, context_id))

        else: 
            context_ulid = ulid.new().str
            cur.execute('''
                INSERT INTO contexts (ULID, text, Section_Num, Section_Title, num_tokens, `Embedding_nomic_1.5`, stop_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (context_ulid, section["text"], section["sec_num"], section["sec_title"], section["tokens"], json.dumps(section["embedding"][0]), "Section"))
            cur.execute('''
                        INSERT INTO sections_contexts (Section_ID, Context_ID)
                        VALUES (?, ?)
                    ''', (section_ulid, context_ulid))

        cur.execute('''
            INSERT INTO article_sections (Article_ID, Section_ID)
            VALUES (?, ?)
        ''', (article_ulid, section_ulid))

    conn.commit()
    conn.close()

    print("Metadata and sections inserted successfully.")


# db_path = 'articles.db'
# initialize_database(db_path)

# insert_data(metadata, total_tokens, grouped_data, db_path)