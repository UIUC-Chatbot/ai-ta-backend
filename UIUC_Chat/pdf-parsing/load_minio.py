import os
import sqlite3
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Manager, Process, Queue

from dotenv import load_dotenv
from minio import Minio # type: ignore
from pdf_process import parse_and_group_by_section, process_pdf_file
from urllib3 import PoolManager
from urllib3.util.retry import Retry

from SQLite import initialize_database, insert_data # type: ignore

load_dotenv(override=True)

# Create a custom PoolManager with desired settings
http_client = PoolManager(
    timeout=300,  # 5 minutes timeout
    maxsize=200,  # Increased pool size
    retries=Retry(total=10, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504]))

client = Minio(
    os.environ['MINIO_API_ENDPOINT'],
    access_key=os.getenv('MINIO_ACCESS_KEY'),
    secret_key=os.getenv('MINIO_SECRET_KEY'),
    secure=True,
    http_client=http_client,
)

LOG_FILE = 'successfully_parsed_files.log'
ERR_LOG_FILE = f'ERRORS_parsed_files.log'

grobid_server = os.getenv('GROBID_SERVER')
BASE_TEMP_DIR = 'temp'
BASE_OUTPUT_DIR = 'output'
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
      insert_data(data['metadata'], data['total_tokens'], data['grouped_data'], data['db_path'], data['references'],
                  data['ref_num_tokens'])

      save_processed_file(LOG_FILE, data['file_name'])
      conn.commit()
    except Exception as e:
      with open(ERR_LOG_FILE, 'a') as f:
        f.write(f"db_worker: {data['file_name']}: {str(e)}\n")
  conn.close()


def minio_object_generator(client, bucket_name):
  processed_files = load_processed_files(LOG_FILE)
  for obj in client.list_objects(bucket_name, recursive=True):
    if obj.object_name not in processed_files:
      yield obj


def main_parallel_upload():
  initialize_database(DB_PATH)
  os.makedirs(BASE_TEMP_DIR, exist_ok=True)
  os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
  # processed_files = load_processed_files(LOG_FILE)

  num_processed_this_run = 0

  manager = Manager()
  queue = manager.Queue()
  db_proc = Process(target=db_worker, args=(queue, DB_PATH))
  db_proc.start()
  with ProcessPoolExecutor(max_workers=80) as executor:
    batch_size = 1_000
    minio_gen = minio_object_generator(client, BUCKET_NAME)

    while True:
      futures = {}
      for _ in range(batch_size):
        try:
          obj = next(minio_gen)
          futures[executor.submit(upload_single_pdf, obj.object_name, queue)] = obj
        except StopIteration:
          break

      if not futures:
        break

      for future in as_completed(futures):
        obj = futures[future]
        try:
          future.result()
          num_processed_this_run += 1
          if num_processed_this_run % 100 == 0: print("Num processed this run:", num_processed_this_run)
        except Exception as e:
          with open(ERR_LOG_FILE, 'a') as f:
            f.write(f"main: {obj.object_name}: {str(e)}\n")
          print(f"Error processing {obj.object_name}: {str(e)}")

      futures.clear()

  queue.put(None)
  db_proc.join()


def upload_single_pdf(minio_object_name, queue):
  """
    This is the fundamental unit of parallelism: upload a single PDF to SQLite, all or nothing.
    """
  try:
    response = client.get_object(BUCKET_NAME, minio_object_name)
    file_content = response.read()
    response.close()
    response.release_conn()

    tmp_file_path = None

    try:
      with tempfile.NamedTemporaryFile() as tmp_file:
        tmp_file.write(file_content)
        tmp_file.flush()

        grobid_config = {
            "grobid_server": grobid_server,
            "batch_size": 100,
            "sleep_time": 5,
            "timeout": 120,
        }

        output_data = process_pdf_file(tmp_file.path, BASE_TEMP_DIR, BASE_OUTPUT_DIR, grobid_config)
        metadata, grouped_data, total_tokens, references, ref_num_tokens = parse_and_group_by_section(output_data)

        queue.put({
            'metadata': metadata,
            'total_tokens': total_tokens,
            'grouped_data': grouped_data,
            'references': references,
            'db_path': DB_PATH,
            'file_name': minio_object_name,
            'ref_num_tokens': ref_num_tokens
        })

    finally:
      if tmp_file_path and os.path.exists(tmp_file_path):
        os.remove(tmp_file_path)

  except Exception as e:
    with open(ERR_LOG_FILE, 'a') as f:
      f.write(f"upload: {minio_object_name}: {str(e)}\n")
      print(f"Error downloading {minio_object_name}: {str(e)}")


if __name__ == '__main__':
  main_parallel_upload()
