from dotenv import load_dotenv

load_dotenv()

import time
import json
import math
import os
import tempfile
import traceback
from typing import Any, Dict, List, Optional

import tiktoken
from bs4 import BeautifulSoup
from doc2json.grobid_client import GrobidClient
from doc2json.tei_to_json import (
    convert_tei_xml_file_to_s2orc_json,
    convert_tei_xml_soup_to_s2orc_json,
)
from embedding import get_embeddings
from posthog import Posthog
from langchain_text_splitters import RecursiveCharacterTextSplitter  # type: ignore

ERR_LOG_FILE = f'ERRORS_parsed_files.log'
grobid_server = os.getenv('GROBID_SERVER')
BASE_TEMP_DIR = 'temp'
BASE_OUTPUT_DIR = 'output'
BASE_LOG_DIR = 'log'

posthog = Posthog(sync_mode=True, project_api_key=os.environ['LLM_GUIDED_RETRIEVAL_POSTHOG_API_KEY'], host='https://us.i.posthog.com')

def process_pdf_stream(input_file: str,
                       sha: str,
                       input_stream: bytes,
                       grobid_config: Optional[Dict] = None) -> Dict | None:
  """
    Process PDF stream
    :param input_file:
    :param sha:
    :param input_stream:
    :return:
    """
  try:
    client = GrobidClient(grobid_config)
    tei_text = client.process_pdf_stream(input_file, input_stream, 'temp', "processFulltextDocument")

    soup = BeautifulSoup(tei_text, "xml")

    paper = convert_tei_xml_soup_to_s2orc_json(soup, input_file, sha)

    return paper.release_json('pdf')
  except Exception as e:
    with open(ERR_LOG_FILE, 'a') as f:
      f.write(f" process_stream: {input_file}: {str(e)}\n")
      print(f"Error process pdf stream {input_file}: {str(e)}")


def process_pdf_file(input_file: os.PathLike,
                     temp_dir: str = BASE_TEMP_DIR,
                     output_dir: str = BASE_OUTPUT_DIR,
                     minio_path: str = '') -> Dict | None:
  """
    Process a PDF file and get JSON representation
    :param input_file:
    :param temp_dir:
    :param output_dir:
    :return:
    """

  tei_file = tempfile.NamedTemporaryFile(dir=temp_dir, delete=False, suffix='.tei.xml')
  output_file = tempfile.NamedTemporaryFile(dir=output_dir, delete=False, suffix='.json')

  tei_file_path = tei_file.name
  output_file_path = output_file.name

  try:
    grobid_config = {
        "grobid_server": grobid_server,
        "batch_size": 2000,
        "sleep_time": 5,
        "generateIDs": False,
        "consolidate_header": False,
        "consolidate_citations": True,
        "include_raw_citations": True,
        "include_raw_affiliations": False,
        "max_workers": 18,
        # IDK if concurrency or n work here, but want to try.
        "concurrency": 18, # slightly more than the 16 threads available, as recommended.
        "n": 18, # slightly more than the 16 threads available, as recommended.
        "timeout": 600,
    }

    start_time = time.monotonic()

    client = GrobidClient(grobid_config)
    client.process_pdf(str(input_file), tei_file.name, "processFulltextDocument")
    print(f"⏰ Grobid Runtime: {(time.monotonic() - start_time):.2f} seconds")
    posthog.capture('llm-guided-ingest',
                  event='grobid_runtime_v2',
                  properties={
                      'runtime_sec': float(f"{(time.monotonic() - start_time):.2f}"),
                      'minio_file': f'{str(minio_path)}',
                      'grobid_using_GPU': True,
                  })

    start_time_convert = time.monotonic()
    assert os.path.exists(tei_file.name)
    paper = convert_tei_xml_file_to_s2orc_json(tei_file.name)
    print(f"⏰ Convert TEI to JSON Runtime: {(time.monotonic() - start_time_convert):.2f} seconds")


    with open(output_file.name, 'w') as outf:
      json.dump(paper.release_json(), outf, indent=4, sort_keys=False)

    # Read the content of the output file and delete it
    with open(output_file.name, 'r') as f:
      output_data = json.load(f)

    os.remove(tei_file_path)
    os.remove(output_file_path)

    return output_data

  except Exception as e:
    print(f"Error in process_pdf_file (with filename: `{input_file}`): {str(e)}")
    traceback.print_exc()

    with open(ERR_LOG_FILE, 'a') as f:
      f.write(f"process pdf: {input_file}: {str(e)}\n")
      print(f"Error process pdf file {input_file}: {str(e)}")

  finally:
    if tei_file_path and os.path.exists(tei_file_path):
      os.remove(tei_file_path)
    if os.path.exists(output_file_path):
      os.remove(output_file_path)


def parse_and_group_by_section(data) -> Any:
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
  references = {}
  ref_num_tokens = {}
  failed_secs = 0

  # with open(filepath, "r") as file:
  #     data = json.load(file)

  metadata = {
      "title": data["title"] if data and "title" in data else None,
      "authors": None if data.get("authors") is None else [
          " ".join(filter(None, [author.get("first"), " ".join(author.get("middle", [])), author.get("last")]))
          for author in data["authors"]
      ],
      "date_published": data["year"],
      "journal": data["venue"],
      "paper_id": data["paper_id"],
      "header": data["header"],
      "year": data["year"],
      "identifiers": data["identifiers"],
      "abstract": data["abstract"],
  }

  try:
    encoding = tiktoken.get_encoding("cl100k_base")

    for key in data["pdf_parse"]["bib_entries"]:
      references[key] = format_reference(data["pdf_parse"]["bib_entries"][key])
      ref_num_tokens[key] = len(encoding.encode(references[key]))
    
    if metadata['abstract']:
      grouped_texts['0'] = metadata['abstract']
      grouped_titles['0'] = 'Abstract'
    
    null_sec = 1
    cur_sec = null_sec
    for entry in data["pdf_parse"]["body_text"]:
      text = entry["text"]
      section = entry["section"]
      sec_num = entry["sec_num"]
      # page_num = entry["page_num"]
      try:
        major_sec_num = math.floor(float(sec_num))
      except Exception:
        major_sec_num = -1
        failed_secs += 1
        # print(f"Failed: {failed_secs}", json.dumps(entry, indent=2))
      
      if not sec_num and section not in grouped_titles.values():
        sec_num = str(null_sec)
        cur_sec = str(null_sec)
        null_sec += 1

      if sec_num:
        if sec_num in grouped_texts:
          grouped_texts[sec_num] += " " + text
          # grouped_pages[sec_num].append(page_num)
        else:
          grouped_texts[sec_num] = text
          grouped_titles[sec_num] = section
          # grouped_pages[sec_num] = [page_num]
      else:
        grouped_texts[cur_sec] += " " + text

      if sec_num:
        all_sections[sec_num] = section

    if not all_sections:
      num = 1
      for i in data["pdf_parse"]["body_text"]:
        grouped_texts[str(num)] = i["text"]
        num += 1

    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        model_name="gpt-4",
        chunk_size=7000,
        chunk_overlap=400,
    )

    valid_keys = [key for key in grouped_texts if key is not None]

    result = []

    for key in sorted(valid_keys):
      section_text = grouped_texts[key]
      section_title = grouped_titles.get(key, None)
      # section_page = grouped_pages.get(key, "Unknown")
      tokens = len(encoding.encode(section_text))

      result.append({
          "text": section_text,
          "sec_num": key,
          "sec_title": section_title,
          "tokens": tokens,
          # "page_num": section_page,
          "chunk_text": [],
          "chunk_tokens": [],
          "embedding": []
      })

      if tokens > 7000:
        chunks = text_splitter.split_text(section_text)
        for i, chunk in enumerate(chunks):
          chunk_tokens = len(encoding.encode(chunk))
          result[-1]["chunk_text"].append(chunk)
          result[-1]["chunk_tokens"].append(chunk_tokens)
      else:
        result[-1]["chunk_text"].append(section_text)
        result[-1]["chunk_tokens"].append(tokens)

      # print("start embedding")
      for i, chunk in enumerate(result[-1]["chunk_text"]):
        context_with_title = f'Section {result[-1]["sec_num"]}: {result[-1]["sec_title"]}\n{chunk}'
        embedding = get_embeddings(context_with_title)
        result[-1]["embedding"].append(embedding)

    total_tokens = sum([entry["tokens"] for entry in result])
    # avg_tokens_per_section = total_tokens / max(len(result), 1)
    # try:
    #     max_tokens_per_section = max([entry["tokens"] for entry in result])
    # except Exception:
    #     max_tokens_per_section = 0

    # return metadata, result, all_sections, total_tokens, avg_tokens_per_section, max_tokens_per_section, references
    return metadata, result, total_tokens, references, ref_num_tokens

  except Exception as e:
    with open(ERR_LOG_FILE, 'a') as f:
      f.write(f"parse_and_group: {data['paper_id']}: {str(e)}\n")
    raise (ValueError(f"Failed parse_and_grou_by_section() with error: {e}"))


def format_reference(reference):
  # Extract individual fields from the reference
  # ref_id = reference['ref_id']
  # title = reference.get('title', '')
  # authors = reference.get('authors', [])
  # year = reference.get('year', '')
  # venue = reference.get('venue', '')
  # volume = reference.get('volume', '')
  # issue = reference.get('issue', '')
  # pages = reference.get('pages', '')
  # other_ids = reference.get('other_ids', {})
  # num = reference.get('num', '')
  urls = reference.get('urls', [])
  raw_text = reference.get('raw_text', '')
  links = reference.get('links', '')

  combined_text = (f"{raw_text}. {urls}. {links}")

  return combined_text
