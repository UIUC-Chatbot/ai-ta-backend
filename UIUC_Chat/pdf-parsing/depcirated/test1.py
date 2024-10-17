import logging
import os
import sqlite3
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Manager, Process

from dotenv import load_dotenv
from pdf_process import parse_and_group_by_section, process_pdf_file
from SQLite import initialize_database, insert_data

from minio import Minio

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
BASE_TEMP_DIR = 'temp'
BASE_OUTPUT_DIR = 'output'
LOG_FILE = 'successfully_parsed_files.log'
ERR_LOG_FILE = 'ERRORS_parsed_files.log'
BUCKET_NAME = 'pubmed'
DB_PATH = 'articles.db'
MAX_WORKERS = 10

# Initialize Minio client
client = Minio(os.getenv('MINIO_API_ENDPOINT'),
               access_key=os.getenv('MINIO_ACCESS_KEY'),
               secret_key=os.getenv('MINIO_SECRET_KEY'),
               secure=True)

# Initialize GROBID server URL
grobid_server = os.getenv('GROBID_SERVER')


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
      queue.task_done()
      break
    try:
      insert_data(data['metadata'], data['total_tokens'], data['grouped_data'], data['object_name'], data['references'],
                  data['ref_num_tokens'])
      save_processed_file(LOG_FILE, data['file_name'])
      conn.commit()
      logger.info(f"Processed and committed {data['file_name']}")
    except Exception as e:
      with open(ERR_LOG_FILE, 'a') as f:
        f.write(f"{data['file_name']}: {str(e)}\n")
      logger.error(f"Error processing {data['file_name']}: {str(e)}")
    finally:
      queue.task_done()
  conn.close()


def main_parallel_upload():
  initialize_database(DB_PATH)
  processed_files = load_processed_files(LOG_FILE)

  manager = Manager()
  queue = manager.Queue()
  db_proc = Process(target=db_worker, args=(queue, DB_PATH))
  db_proc.start()

  with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {}
    for obj in client.list_objects(BUCKET_NAME, recursive=True):
      if obj.object_name not in processed_files:
        response = client.get_object(BUCKET_NAME, obj.object_name)
        futures[executor.submit(upload_single_pdf, obj.object_name, response, queue)] = obj

    for future in as_completed(futures):
      obj = futures[future]
      try:
        future.result()
      except Exception as e:
        with open(ERR_LOG_FILE, 'a') as f:
          f.write(f"{obj.object_name}: {str(e)}\n")
        logger.error(f"Error processing {obj.object_name}: {str(e)}")

  queue.put(None)
  queue.join()
  db_proc.join()


def upload_single_pdf(minio_object_name, response, queue):
  try:
    with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
      for chunk in response.stream(1024 * 1024):
        tmp_file.write(chunk)
      tmp_file.flush()

      grobid_config = {"grobid_server": grobid_server, "batch_size": 2500, "sleep_time": 5, "timeout": 60}
      os.makedirs(BASE_TEMP_DIR, exist_ok=True)
      os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
      output_data = process_pdf_file(tmp_file.name, BASE_TEMP_DIR, BASE_OUTPUT_DIR, grobid_config)
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
      logger.info(f"Queued {minio_object_name} for database insertion")

  except Exception as e:
    with open(ERR_LOG_FILE, 'a') as f:
      f.write(f"{minio_object_name}: {str(e)}\n")
    logger.error(f"Error processing {minio_object_name}: {str(e)}")


if __name__ == '__main__':
  main_parallel_upload()
