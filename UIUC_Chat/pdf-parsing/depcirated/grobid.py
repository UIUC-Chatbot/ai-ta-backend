# git clone https://github.com/kermitt2/grobid_client_python
# cd grobid_client_python
# python3 setup.py install

# from grobid_client.grobid_client import GrobidClient
import json
import math
import os
import uuid
from os import PathLike
from pathlib import Path
from typing import Dict, Optional

import ray
import tiktoken
from allenai_grobid_parser import process_pdf_file
from SQLite import insert_grobid_metadata

from ai_ta_backend.utils.types import GrobidMetadata


def main(pdf_dir: PathLike):
  pdf_paths = []
  for root, dirs, files in os.walk(pdf_dir):
    for file in files:
      if file.endswith(".pdf"):
        pdf_paths.append(os.path.join(root, file))

  ray.init()
  futures = [runGrobid.remote(pdf) for pdf in pdf_paths]
  all_results = ray.get(futures)
  print("All results:", all_results)


@ray.remote
def runGrobid(pdf_path: PathLike):
  """
  Use ALLenAI's Grobid wrapper: https://github.com/allenai/s2orc-doc2json

  I used: 
  $ python doc2json/grobid2json/process_pdf.py -i tests/pdf/N18-3011.pdf -t temp_dir/ -o output_dir/

  But would be better to do this in python... maybe capture the JSON directly without writing to disk.
  """

  final_json: Dict = process_pdf_file(pdf_path, 'tmp-grobid')
  # print("Final JSON:", json.dumps(final_json, indent=2))
  result, all_sections, total_tokens, avg_tokens_per_section, max_tokens_per_section = parse_and_group_by_section(
      final_json)

  file = GrobidMetadata(
      uuid=str(uuid.uuid4()),
      filepath=str(pdf_path),  # TODO use minio prefix
      total_tokens=total_tokens,
      all_sections=all_sections,
      additional_fields=result,
      avg_tokens_per_section=int(avg_tokens_per_section),
      max_tokens_per_section=max_tokens_per_section)

  insert_grobid_metadata(file, commit_on_change=True)
  print("✅ Done: ", pdf_path)


def parse_and_group_by_section(data: Dict):
  """
  This parses the output of AllenAI's Grobid wrapper. https://github.com/allenai/s2orc-doc2json

  # TODO Capture Abstract, authors, bibliography... maybe more.

  Output format is two dictionaries: 
  * Full text grouped by major section. 
  * The "outline:" all the section titles, including minor sections. This might be useful as a separate embedding. 

  Text grouped by major section:
  {
    "all_text": "The goal of this work...",
    "major_sec_num": 1,
    "major_sec_title": "Introduction"
  },
  {
    "all_text": "The literature graph is a property graph with directed edges...",
    "major_sec_num": 2,
    "major_sec_title": "Structure of The Literature Graph"
  }
  ...

  All sections (including minor sections):
  {
    "1": "Introduction",
    "2": "Structure of The Literature Graph",
    "2.1": "Node Types",
    "2.2": "Edge Types",
    "3": "Extracting Metadata",
    "4": "Entity Extraction and Linking",
    "4.1": "Approaches",
    "4.2": "Entity Extraction Models",
    "4.3": "Knowledge Bases",
    "4.4": "Entity Linking Models",
    "5": "Other Research Problems",
    "6": "Conclusion and Future Work",
    "null": ""
  }
  """

  grouped_texts = {}
  grouped_titles = {}
  all_sections = {}
  failed_secs = 0

  # with open(filepath, "r") as file:
  #   data = json.load(file)

  # Iterate over each entry in the body text
  for entry in data["pdf_parse"]["body_text"]:
    text = entry["text"]
    section = entry["section"]
    sec_num = entry["sec_num"]
    try:
      major_sec_num = math.floor(float(sec_num))  # Extract the main section number using floor function
    except Exception:
      major_sec_num = -1
      failed_secs += 1
      # print(f"Failed: {failed_secs}", json.dumps(entry, indent=2))

    # Append text and update title for the corresponding section group
    if major_sec_num in grouped_texts:
      grouped_texts[major_sec_num] += " " + text
    else:
      grouped_texts[major_sec_num] = text
      grouped_titles[major_sec_num] = section

    # Update all sections with both major and minor sections
    if sec_num:
      all_sections[sec_num] = section

  encoding = tiktoken.get_encoding("cl100k_base")

  # Format result as a list of dictionaries
  result = [
      {
          "text": grouped_texts[key],
          "major_sec_num": key,
          # "major_sec_title": grouped_titles.get(key, "Misc"),
          "major_sec_title": grouped_titles.get(key) if grouped_titles.get(key) else "misc",
          "tokens": len(encoding.encode(grouped_texts[key]))
      } for key in sorted(grouped_texts)
  ]

  total_tokens = sum([entry["tokens"] for entry in result])
  avg_tokens_per_section = total_tokens / max(len(result), 1)
  try:
    max_tokens_per_section = max([entry["tokens"] for entry in result])
  except Exception:
    max_tokens_per_section = 0

  return result, all_sections, total_tokens, avg_tokens_per_section, max_tokens_per_section


if __name__ == "__main__":
  # Call the function and print the result
  main(Path("/Users/kastanday/code/ncsa/ai-ta/ai-ta-backend/science-pdfs"))

  # filepath = Path("/Users/kastanday/code/ncsa/ai-ta/ai-experiments/s2orc-doc2json/output_dir/N18-3011.json")
  # grouped_data, all_sections, total_tokens = parse_and_group_by_section(filepath)
  # print("Main result:", json.dumps(grouped_data, indent=2))
  # print("All sections:", json.dumps(all_sections, indent=2))
  # print("total_tokens:", total_tokens)

  # insert_grobid_metadata(GrobidMetadata(total_tokens=total_tokens,
  #                                       all_sections=all_sections,
  #                                       additional_fields=grouped_data),
  #                        commit_on_change=True)
