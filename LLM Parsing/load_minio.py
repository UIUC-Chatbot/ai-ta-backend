from dotenv import load_dotenv
load_dotenv()

import tempfile
from minio import Minio
import os
from combine import process_pdf_file, parse_and_group_by_section, insert_data, initialize_database

BASE_TEMP_DIR = 'temp'
BASE_OUTPUT_DIR = 'output'

client = Minio(
    os.getenv('MINIO_API_ENDPOINT'),
    access_key=os.getenv('MINIO_ACCESS_KEY'),
    secret_key=os.getenv('MINIO_SECRET_KEY'),
    secure=True
)
grobid_server = os.getenv('GROBID_SERVER')

bucket_name = 'small-science'
LOG_FILE = 'minio_downloaded_files.log'
ERR_LOG_FILE = f'ERRORS_{LOG_FILE}'

def load_processed_files(log_file):
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            return set(line.strip() for line in f)
    return set()

def save_processed_file(log_file, file_path):
    with open(log_file, 'a') as f:
        f.write(f"{file_path}\n")

db_path = 'articles.db'
initialize_database(db_path)

processed_files = load_processed_files(LOG_FILE)
objects = client.list_objects(bucket_name, recursive=True)

for obj in objects:
    if obj.object_name not in processed_files:
        try: 
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, obj.object_name)
            os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
            with open(temp_file_path, 'wb') as tmp_file:
                client.fget_object(bucket_name, obj.object_name, tmp_file.name)
                print(f"Downloaded {obj.object_name}")
                save_processed_file(LOG_FILE, obj.object_name)
                grobid_config = {
                "grobid_server": grobid_server,
                "batch_size": 1000,
                "sleep_time": 5,
                "timeout": 60
                }
                temp_path = BASE_TEMP_DIR
                output_path = BASE_OUTPUT_DIR

                os.makedirs(temp_path, exist_ok=True)
                os.makedirs(output_path, exist_ok=True)
                output_file = process_pdf_file(tmp_file.name, temp_path, output_path, grobid_config)
                metadata, grouped_data, all_sections, total_tokens, avg_tokens_per_section, max_tokens_per_section = parse_and_group_by_section(output_file.name)
                # print("Metadata:", metadata)
                # print("Number of tokens per section:")
                #   for section in grouped_data:
                #     print(f"Section {section['sec_num']} ({section['sec_title']}): {section['tokens']} tokens")
                # print("All sections:", json.dumps(all_sections, indent=2))
                #   print("Total tokens:", total_tokens)
                #   print("Average tokens per section:", avg_tokens_per_section)
                #   print("Max tokens per section:", max_tokens_per_section)
                insert_data(metadata, total_tokens, grouped_data, db_path)
                # break

        except Exception as e:
            with open(ERR_LOG_FILE, 'a') as f:
                f.write(f"{obj.object_name}: {str(e)}\n")
                print(f"Error downloading {obj.object_name}: {str(e)}")