from concurrent.futures import ProcessPoolExecutor, as_completed
import sqlite3
import time
from dotenv import load_dotenv
load_dotenv()

import tempfile
from minio import Minio
import os
import json
from pdf_process import process_pdf_file, parse_and_group_by_section
from SQLite import initialize_database, insert_data
from multiprocessing import Process, Queue, Manager
# files to do list.... but that's stored in minio... 

BASE_TEMP_DIR = 'temp'
BASE_OUTPUT_DIR = 'output'
client = Minio(
        os.getenv('MINIO_API_ENDPOINT'),
        access_key=os.getenv('MINIO_ACCESS_KEY'),
        secret_key=os.getenv('MINIO_SECRET_KEY'),
        secure=True
    )
grobid_server = os.getenv('GROBID_SERVER')
LOG_FILE = 'successfully_parsed_files.log'
ERR_LOG_FILE = f'ERRORS_parsed_files.log'
BUCKET_NAME = 'small-science'
DB_PATH = 'articles.db'


def load_processed_files(log_file):
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            return set(line.strip() for line in f)
    return set()

def save_processed_file(log_file, file_path):
    with open(log_file, 'a') as f:
        f.write(f"{file_path}\n")

def db_worker(queue, db_path):  # EDIT: Added db_worker function
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    while True:
        data = queue.get()
        if data is None:
            break
        try:
            insert_data(data['metadata'], data['total_tokens'], data['grouped_data'], data['object_name'])
            # save_processed_file(LOG_FILE, data['object_name'])
            save_processed_file(LOG_FILE, data['file_name'])
            conn.commit()
        except Exception as e:
            with open(ERR_LOG_FILE, 'a') as f:
                f.write(f"{data['object_name']}: {str(e)}\n")
    conn.close()

def main_parallel_upload():
    initialize_database(DB_PATH)
    folder_name = '83500000/10.21767/'
    processed_files = load_processed_files(LOG_FILE)
    objects = client.list_objects(BUCKET_NAME, recursive=True, prefix=folder_name)
    
    start_time = time.monotonic()
    
    manager = Manager()
    queue = manager.Queue()
    db_proc = Process(target=db_worker, args=(queue, DB_PATH))
    db_proc.start()

    with ProcessPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(upload_single_pdf, obj, queue): obj for obj in objects if obj.object_name not in processed_files}
        for future in as_completed(futures):
            obj = futures[future]
            try:
                future.result()
            except Exception as e:
                with open(ERR_LOG_FILE, 'a') as f:
                    f.write(f"{obj.object_name}: {str(e)}\n")
                print(f"Error processing {obj.object_name}: {str(e)}")
    
    queue.put(None)
    db_proc.join()
    print(f"Total Runtime: {(time.monotonic() - start_time):.2f} seconds")

def upload_single_pdf(minio_object, queue):
    """
    This is the fundamental unit of parallelism: upload a single PDF to SQLite, all or nothing.
    """
    try: 
        start_time = time.monotonic()
        temp_dir = tempfile.gettempdir()
        temp_file_path = os.path.join(temp_dir, minio_object.object_name)
        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
        with open(temp_file_path, 'wb') as tmp_file:
            client.fget_object(BUCKET_NAME, minio_object.object_name, tmp_file.name)
            print(f"Downloaded {minio_object.object_name}")
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
            queue.put({
                'metadata': metadata,
                'total_tokens': total_tokens,
                'grouped_data': grouped_data,
                'object_name': DB_PATH,
                'file_name': minio_object.object_name
            })
            # print("Metadata:", metadata)
            # print("grouped data: ", grouped_data)
            # print("Number of tokens per section:")
            # for section in grouped_data:
            #     print(f"Section {section['sec_num']} ({section['sec_title']}): {section['tokens']} tokens")
            # print("All sections:", json.dumps(all_sections, indent=2))
            # print("Total tokens:", total_tokens)
            # print("Average tokens per section:", avg_tokens_per_section)
            # print("Max tokens per section:", max_tokens_per_section)
            # insert_data(metadata, total_tokens, grouped_data, DB_PATH)
            # save_processed_file(LOG_FILE, minio_object.object_name)
            print(f"Single Task Runtime: {(time.monotonic() - start_time):.2f} seconds")

            # TODO: LOGS SUCCESSES

    except Exception as e:
        with open(ERR_LOG_FILE, 'a') as f:
            f.write(f"{minio_object.object_name}: {str(e)}\n")
            print(f"Error downloading {minio_object.object_name}: {str(e)}")

if __name__ == '__main__':  
    main_parallel_upload()