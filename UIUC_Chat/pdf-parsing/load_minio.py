from concurrent.futures import ProcessPoolExecutor, as_completed
import sqlite3
import time
from dotenv import load_dotenv
load_dotenv()

import tempfile
from minio import Minio
import os
import psutil
import json
from pdf_process import process_pdf_file, parse_and_group_by_section
from SQLite import initialize_database, insert_data
from multiprocessing import Process, Queue, Manager
import resource

# def print_memory_usage_before():
#     usage = resource.getrusage(resource.RUSAGE_SELF)
#     print(f"Memory usage before: {usage.ru_maxrss} KB")

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
BUCKET_NAME = 'pubmed'
DB_PATH = 'articles.db'


def load_processed_files(log_file):
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            return set(line.strip() for line in f)
    return set()

def save_processed_file(log_file, file_path):
    with open(log_file, 'a') as f:
        f.write(f"{file_path}\n")

def db_worker(queue, db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    cursor = conn.cursor()
    while True:
        data = queue.get()
        if data is None:
            break
        try:
            insert_data(data['metadata'], data['total_tokens'], data['grouped_data'], data['object_name'], data['references'], data['ref_num_tokens'])

            save_processed_file(LOG_FILE, data['file_name'])
            conn.commit()
        except Exception as e:
            with open(ERR_LOG_FILE, 'a') as f:
                f.write(f"{data['file_name']}: {str(e)}\n")
    conn.close()

def main_parallel_upload():
    initialize_database(DB_PATH)
    # folder_name = '83500000/10.21767/'
    processed_files = load_processed_files(LOG_FILE)
    
    manager = Manager()
    queue = manager.Queue()
    db_proc = Process(target=db_worker, args=(queue, DB_PATH))
    db_proc.start()

    # processed_count_pubmed = 0
    # max_count = 50

    with ProcessPoolExecutor(max_workers=20) as executor:
        futures = {}


        for obj in client.list_objects(BUCKET_NAME, recursive=True):
            # if processed_count_pubmed >= max_count:
            #     break
            if obj.object_name not in processed_files:
                response = client.get_object(BUCKET_NAME, obj.object_name)
                file_content = response.read()
                response.close()
                response.release_conn()
                # print_memory_usage_before()
                futures[executor.submit(upload_single_pdf, obj.object_name, file_content, queue)] = obj
                # processed_count_pubmed += 1

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

def upload_single_pdf(minio_object_name, file_content, queue):
    """
    This is the fundamental unit of parallelism: upload a single PDF to SQLite, all or nothing.
    """
    try:
        
        with tempfile.NamedTemporaryFile() as tmp_file:
            tmp_file.write(file_content)
            tmp_file.flush()

            grobid_config = {
                "grobid_server": grobid_server,
                "batch_size": 2500,
                "sleep_time": 5,
                "timeout": 60
            }
            temp_path = BASE_TEMP_DIR
            output_path = BASE_OUTPUT_DIR

            os.makedirs(temp_path, exist_ok=True)
            os.makedirs(output_path, exist_ok=True)
            output_data = process_pdf_file(tmp_file.name, temp_path, output_path, grobid_config)
            metadata, grouped_data, total_tokens, references, ref_num_tokens = parse_and_group_by_section(output_data)

            
            queue.put({
                'metadata': metadata,
                'total_tokens': total_tokens,
                'grouped_data': grouped_data,
                'references': references,
                'object_name': DB_PATH,
                'file_name': minio_object_name,
                'ref_num_tokens': ref_num_tokens
            })

    except Exception as e:
        with open(ERR_LOG_FILE, 'a') as f:
            f.write(f"{minio_object_name}: {str(e)}\n")
            print(f"Error downloading {minio_object_name}: {str(e)}")

if __name__ == '__main__':  
    main_parallel_upload()