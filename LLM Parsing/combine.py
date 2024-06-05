from dotenv import load_dotenv
load_dotenv()

import argparse
import json
import os
import time
from typing import Dict, Optional, List
import sqlite3
import tempfile
from langchain_text_splitters import RecursiveCharacterTextSplitter

from bs4 import BeautifulSoup
from doc2json.grobid2json.grobid.grobid_client import GrobidClient
from doc2json.grobid2json.tei_to_json import (
    convert_tei_xml_file_to_s2orc_json,
    convert_tei_xml_soup_to_s2orc_json,
)
grobid_server = os.getenv('GROBID_SERVER')
BASE_TEMP_DIR = 'temp'
BASE_OUTPUT_DIR = 'output'
BASE_LOG_DIR = 'log'

def process_pdf_stream(input_file: str, sha: str, input_stream: bytes, grobid_config: Optional[Dict] = None) -> Dict:
  """
    Process PDF stream
    :param input_file:
    :param sha:
    :param input_stream:
    :return:
    """
  
  client = GrobidClient(grobid_config)
  tei_text = client.process_pdf_stream(input_file, input_stream, 'temp', "processFulltextDocument")

  soup = BeautifulSoup(tei_text, "xml")

  paper = convert_tei_xml_soup_to_s2orc_json(soup, input_file, sha)

  return paper.release_json('pdf')


def process_pdf_file(
    input_file: os.PathLike,
    temp_dir: str = BASE_TEMP_DIR,
    output_dir: str = BASE_OUTPUT_DIR,
    grobid_config: Optional[Dict] = None) -> Dict:
  """
    Process a PDF file and get JSON representation
    :param input_file:
    :param temp_dir:
    :param output_dir:
    :return:
    """
    
  os.makedirs(temp_dir, exist_ok=True)
  os.makedirs(output_dir, exist_ok=True)

  # get paper id as the name of the file
  paper_id = '.'.join(str(input_file).split('/')[-1].split('.')[:-1])
  tei_file = tempfile.NamedTemporaryFile(suffix=f'{paper_id}.tei.xml', dir=temp_dir)
  output_file = tempfile.NamedTemporaryFile(suffix=f'{paper_id}.json', dir=output_dir)

  if not os.path.exists(input_file):
    raise FileNotFoundError(f"{input_file} doesn't exist")
#   if os.path.exists(output_file.name):
#       print(f'{output_file.name} already exists!')
  grobid_config = {
    "grobid_server": "grobid_server",
    "batch_size": 1000,
    "sleep_time": 5,
    "generateIDs": False,
    "consolidate_header": False,
    "consolidate_citations": False,
    "include_raw_citations": True,
    "include_raw_affiliations": False,
    "max_workers": 2,
}
  # process PDF through Grobid -> TEI.XML
  client = GrobidClient(grobid_config)
  client.process_pdf(str(input_file), tei_file.name, "processFulltextDocument")
  # process TEI.XML -> JSON
  assert os.path.exists(tei_file.name)
  paper = convert_tei_xml_file_to_s2orc_json(tei_file.name)

#   return paper.release_json()
  # # write to file
  with open(output_file.name, 'w') as outf:
      json.dump(paper.release_json(), outf, indent=4, sort_keys=False)
  return output_file



  # git clone https://github.com/kermitt2/grobid_client_python
# cd grobid_client_python
# python3 setup.py install

# from grobid_client.grobid_client import GrobidClient
import json
import math
from pathlib import Path
from typing import Dict
import tiktoken

def parse_and_group_by_section(filepath):
    """
    This parses the output of AllenAI's Grobid wrapper. https://github.com/allenai/s2orc-doc2json

    Output format is two dictionaries: 
    * Full text grouped by major section. 
    * The "outline:" all the section titles, including minor sections. This might be useful as a separate embedding. 
    """
    grouped_texts = {}
    grouped_titles = {}
    grouped_pages = {}
    all_sections = {}
    failed_secs = 0

    with open(filepath, "r") as file:
        data = json.load(file)

    # print(data.keys())

    # #new
    metadata = {
        "title": data["title"],
        "authors": [
            " ".join(filter(None, [author["first"], " ".join(author["middle"]), author["last"]]))
            for author in data["authors"]
        ],
        "date_published": data["year"],
        "journal": data["venue"]
    }

    # Iterate over each entry in the body text
    for entry in data["pdf_parse"]["body_text"]:
        text = entry["text"]
        section = entry["section"]
        sec_num = entry["sec_num"]
        # page_num = entry["page_num"]
        try:
            major_sec_num = math.floor(float(sec_num))  # Extract the main section number using floor function
        except Exception:
            major_sec_num = -1
            failed_secs += 1
            # print(f"Failed: {failed_secs}", json.dumps(entry, indent=2))

        if sec_num in grouped_texts:
            grouped_texts[sec_num] += " " + text
            # grouped_pages[sec_num].append(page_num)
        else:
            grouped_texts[sec_num] = text
            grouped_titles[sec_num] = section
            # grouped_pages[sec_num] = [page_num]

        if sec_num:
            all_sections[sec_num] = section

    encoding = tiktoken.get_encoding("cl100k_base")

    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        model_name="gpt-4",
        chunk_size=8192,
        chunk_overlap=400,
    )

    valid_keys = [key for key in grouped_texts if key is not None]

    result = []

    for key in sorted(valid_keys):
        section_text = grouped_texts[key]
        section_title = grouped_titles.get(key, "misc")
        # section_page = grouped_pages.get(key, "Unknown")
        tokens = len(encoding.encode(section_text))

        result.append({
                "text": section_text,
                "sec_num": key,
                "sec_title": section_title,
                "tokens": tokens,
                # "page_num": section_page,
                "chunk_text": [],
                "chunk_tokens": []
            })

        if tokens > 8192:
            chunks = text_splitter.split_text(section_text)
            for i, chunk in enumerate(chunks):
                chunk_tokens = len(encoding.encode(chunk))
                result[-1]["chunk_text"].append(chunk)
                result[-1]["chunk_tokens"].append(chunk_tokens)

    total_tokens = sum([entry["tokens"] for entry in result])
    avg_tokens_per_section = total_tokens / max(len(result), 1)
    try:
        max_tokens_per_section = max([entry["tokens"] for entry in result])
    except Exception:
        max_tokens_per_section = 0

    return metadata, result, all_sections, total_tokens, avg_tokens_per_section, max_tokens_per_section


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Run S2ORC PDF2JSON")
  parser.add_argument("-i", "--input", default='/Users/jackhuang/Desktop/UIUC_Chat/pdf/2303.14186.pdf', help="path to the input PDF file")
  parser.add_argument("-t", "--temp", default=BASE_TEMP_DIR, help="path to the temp dir for putting tei xml files")
  parser.add_argument("-o", "--output", default=BASE_OUTPUT_DIR, help="path to the output dir for putting json files")
  parser.add_argument("-k", "--keep", action='store_true')

  args = parser.parse_args()

  input_path = args.input
  temp_path = args.temp
  output_path = args.output
  keep_temp = args.keep

  start_time = time.time()

  grobid_config = {
    "grobid_server": grobid_server,
    "batch_size": 1000,
    "sleep_time": 5,
    "timeout": 60
  }

  os.makedirs(temp_path, exist_ok=True)
  os.makedirs(output_path, exist_ok=True)

  output_file = process_pdf_file(input_path, temp_path, output_path, grobid_config)

#   runtime = round(time.time() - start_time, 3)
#   print("runtime: %s seconds " % (runtime))
  print('process done.')

#   filepath = Path("/Users/jackhuang/Desktop/UIUC_Chat/allenai/output/2303.14186.json")
  metadata, grouped_data, all_sections, total_tokens, avg_tokens_per_section, max_tokens_per_section = parse_and_group_by_section(output_file.name)
  print("Metadata:", metadata)
#   print("Number of tokens per section:")
#   for section in grouped_data:
#     print(f"Section {section['sec_num']} ({section['sec_title']}): {section['tokens']} tokens")
#     print(f"Page number: {section['page_num']}")
#   print("All sections:", json.dumps(all_sections, indent=2))
#   print("Total tokens:", total_tokens)
#   print("Average tokens per section:", avg_tokens_per_section)
#   print("Max tokens per section:", max_tokens_per_section)




import os
import sqlite3


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

# authors_str = ', '.join(metadata['authors'])

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
        # print(section["tokens"], section["sec_num"], section["sec_title"])
        cur.execute('''
            INSERT INTO sections (num_tokens, Section_Num, Section_Title)
            VALUES (?, ?, ?)
        ''', (section["tokens"], section["sec_num"], section["sec_title"]))
        section_id = cur.lastrowid

        if section["tokens"] > 8192:
            chunks = section["chunk_text"]
            for i, chunk in enumerate(chunks):
                context_id = cur.lastrowid
                chunk_tokens = section["chunk_tokens"][i]
                cur.execute('''
                    INSERT INTO contexts (text, Section_Num, Section_Title, num_tokens, stop_reason)
                    VALUES (?, ?, ?, ?, ?)
                ''', (chunk, section["sec_num"], section["sec_title"], chunk_tokens, "Token limit"))
                context_id = cur.lastrowid

                cur.execute('''
                    INSERT INTO sections_contexts (Section_ID, Context_ID)
                    VALUES (?, ?)
                ''', (section_id, context_id))
        
        else: 
            cur.execute('''
                INSERT INTO contexts (text, Section_Num, Section_Title, num_tokens, stop_reason)
                VALUES (?, ?, ?, ?, ?)
            ''', (section["text"], section["sec_num"], section["sec_title"], section["tokens"], "Section"))
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