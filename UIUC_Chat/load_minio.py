from multiprocessing import Queue, Process, current_process
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

# Global constants
BASE_TEMP_DIR = 'temp'
BASE_OUTPUT_DIR = 'output'
LOG_FILE = 'minio_downloaded_files.log'
ERR_LOG_FILE = f'ERRORS_{LOG_FILE}'
BUCKET_NAME = 'small-science'
DB_PATH = 'articles.db'

client = Minio(
    os.getenv('MINIO_API_ENDPOINT'),
    access_key=os.getenv('MINIO_ACCESS_KEY'),
    secret_key=os.getenv('MINIO_SECRET_KEY'),
    secure=True
)

grobid_server = os.getenv('GROBID_SERVER')

def load_processed_files(log_file):
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            return set(line.strip() for line in f)
    return set()

def save_processed_file(log_file, file_path):
    with open(log_file, 'a') as f:
        f.write(f"{file_path}\n")

def insert_data_with_retry(metadata, total_tokens, grouped_data, db_path, retries=5, wait=1):
    for attempt in range(retries):
        try:
            insert_data(metadata, total_tokens, grouped_data, db_path)
            return
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                time.sleep(wait)
                continue
            else:
                raise
    raise Exception("Max retries exceeded")

def database_writer(queue, db_path):
    while True:
        data = queue.get()
        if data == "DONE":
            break
        metadata, total_tokens, grouped_data = data
        insert_data_with_retry(metadata, total_tokens, grouped_data, db_path)

def main_parallel_upload():
    initialize_database(DB_PATH)
    processed_files = load_processed_files(LOG_FILE)
    folder_name = '83500000/10.21767/'
    objects = client.list_objects(BUCKET_NAME, recursive=True, prefix=folder_name)

    queue = Queue()
    writer_process = Process(target=database_writer, args=(queue, DB_PATH))
    writer_process.start()

    start_time = time.monotonic()
    with ProcessPoolExecutor(max_workers=20, initializer=worker_initializer, initargs=(queue,)) as executor:
        futures = {executor.submit(upload_single_pdf, obj): obj for obj in objects if obj.object_name not in processed_files}
        for future in as_completed(futures):
            obj = futures[future]
            try:
                future.result()
            except Exception as e:
                with open(ERR_LOG_FILE, 'a') as f:
                    f.write(f"{obj.object_name}: {str(e)}\n")
                print(f"Error processing {obj.object_name}: {str(e)}")

    queue.put("DONE")
    writer_process.join()
    print(f"Runtime: {(time.monotonic() - start_time):.2f} seconds")

def worker_initializer(q):
    global queue
    queue = q

def upload_single_pdf(minio_object):
    try:
        start_time = time.monotonic()
        temp_dir = tempfile.gettempdir()
        temp_file_path = os.path.join(temp_dir, minio_object.object_name)
        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)

        with open(temp_file_path, 'wb') as tmp_file:
            client.fget_object(BUCKET_NAME, minio_object.object_name, tmp_file.name)
            print(f"Downloaded {minio_object.object_name}")
            save_processed_file(LOG_FILE, minio_object.object_name)
            
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

            queue.put((metadata, total_tokens, grouped_data))
            print(f"Single Task Runtime: {(time.monotonic() - start_time):.2f} seconds")
    except Exception as e:
        with open(ERR_LOG_FILE, 'a') as f:
            f.write(f"{minio_object.object_name}: {str(e)}\n")
        print(f"Error processing {minio_object.object_name}: {str(e)}")

if __name__ == '__main__':
    main_parallel_upload()
