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
    "grobid_server": grobid_server,
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

    # #new
    metadata = {
        "title": data["title"],
        "authors": [
            " ".join(filter(None, [author["first"], " ".join(author["middle"]), author["last"]]))
            for author in data["authors"]
        ],
        "date_published": data["year"],
        "journal": data["venue"],
        "paper_id": data["paper_id"],
        "header": data["header"],
        "year": data["year"],
        "identifiers": data["identifiers"],
        "abstract": data["abstract"],
        "pdf_parse": data["pdf_parse"],
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

    if not all_sections:
        num = 0
        for i in metadata["pdf_parse"]["body_text"]:
            grouped_texts[str(num)] = i["text"]
            num += 1
    
    # print(grouped_texts)


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
