# git clone https://github.com/kermitt2/grobid_client_python
# cd grobid_client_python
# python3 setup.py install

# from grobid_client.grobid_client import GrobidClient
import json
import math
from os import PathLike
from pathlib import Path
from typing import Optional

import tiktoken

from ai_ta_backend.utils.types import GrobidMetadata
from SQLite import insert_grobid_metadata


def runGrobid(pdf_dir: PathLike, output_dir: Optional[PathLike] = None):
  """
  Use ALLenAI's Grobid wrapper: https://github.com/allenai/s2orc-doc2json

  I used: 
  $ python doc2json/grobid2json/process_pdf.py -i tests/pdf/N18-3011.pdf -t temp_dir/ -o output_dir/

  But would be better to do this in python... maybe capture the JSON directly without writing to disk.
  """
  pass
  # client = GrobidClient(config_path="./config.json")
  # client.process("processFulltextDocument", input_path=pdf_dir, output=output_dir, n=20)


def parse_and_group_by_section(filepath: PathLike):
  """
  This parses the output of AllenAI's Grobid wrapper. https://github.com/allenai/s2orc-doc2json

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

  with open(filepath, "r") as file:
    data = json.load(file)

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

  return result, all_sections, total_tokens


if __name__ == "__main__":
  # Call the function and print the result
  filepath = Path("/Users/kastanday/code/ncsa/ai-ta/ai-experiments/s2orc-doc2json/output_dir/N18-3011.json")
  grouped_data, all_sections, total_tokens = parse_and_group_by_section(filepath)
  print("Main result:", json.dumps(grouped_data, indent=2))
  print("All sections:", json.dumps(all_sections, indent=2))
  print("total_tokens:", total_tokens)

  insert_grobid_metadata(GrobidMetadata(total_tokens=total_tokens,
                                        all_sections=all_sections,
                                        additional_fields=grouped_data),
                         commit_on_change=True)
