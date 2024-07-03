import json
import os

from pdf_process import parse_and_group_by_section, process_pdf_file

from SQLite import initialize_database, insert_data

BASE_TEMP_DIR = 'temp'
BASE_OUTPUT_DIR = 'output'
temp_path = BASE_TEMP_DIR
output_path = BASE_OUTPUT_DIR
input_path = '/home/guest/ai-ta-backend/UIUC_Chat/pdf-parsing/pdf/00010-2022.PMC9059131.pdf'

grobid_config = {"grobid_server": 'https://grobid.kastan.ai', "batch_size": 1000, "sleep_time": 5, "timeout": 60}

os.makedirs(temp_path, exist_ok=True)
os.makedirs(output_path, exist_ok=True)

output_data = process_pdf_file(input_path, temp_path, output_path, grobid_config)
print('process done.')

metadata, grouped_data, total_tokens, references, ref_num_tokens = parse_and_group_by_section(output_data)

print('parse done.')

db_path = 'articles.db'
initialize_database(db_path)

insert_data(metadata, total_tokens, grouped_data, db_path, references, ref_num_tokens)
