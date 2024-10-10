import os
import time
import sqlite3
import tempfile
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Manager, Process, Queue
from pathlib import Path

from dotenv import load_dotenv
from minio import Minio  # type: ignore
from pdf_process import parse_and_group_by_section, process_pdf_file
from urllib3 import PoolManager
from urllib3.util.retry import Retry
from posthog import Posthog
import sentry_sdk
from doc2json.grobid_client import GrobidClient

from SQLite import initialize_database, insert_data  # type: ignore

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv(override=True)

posthog = Posthog(sync_mode=True, project_api_key=os.environ['LLM_GUIDED_RETRIEVAL_POSTHOG_API_KEY'], host='https://us.i.posthog.com')

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
sentry_sdk.init(
    dsn=os.environ['SENTRY_DSN'],
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

# LOG_FILE = 'SUCCESS_parsed_files.log'
# ERR_LOG_FILE = f'ERRORS_parsed_files.log'
LOG_FILE = 'v2-SUCCESS_parsed_files.log'
ERR_LOG_FILE = f'v2-ERRORS_parsed_files.log'
DB_PATH = 'v2-articles.db'

grobid_server = os.getenv('GROBID_SERVER')
BASE_TEMP_DIR = 'temp'
BASE_OUTPUT_DIR = 'output'
BUCKET_NAME = 'pubmed'
# DB_PATH = 'articles.db'

NUM_PARALLEL=70

# Configure Grobid
grobid_config = {
    "grobid_server": os.getenv('GROBID_SERVER'),
    "batch_size": 2000,
    "sleep_time": 3,
    "generateIDs": False,
    "consolidate_header": False,
    "consolidate_citations": False,
    # "include_raw_citations": True,
    "include_raw_citations": False,
    "include_raw_affiliations": False,
    "timeout": 600,
    "n": NUM_PARALLEL,
    "max_workers": NUM_PARALLEL,
}
grobidClient = GrobidClient(grobid_config)


def main_parallel_upload():
  initialize_database(DB_PATH)
  os.makedirs(BASE_TEMP_DIR, exist_ok=True)
  os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
  start_time_main_parallel = time.monotonic()

  num_processed_this_run = 0

  manager = Manager()
  queue = manager.Queue()
  db_proc = Process(target=db_worker, args=(queue, DB_PATH))
  db_proc.start()

  # process to monitor queue size
  # queue_monitor_proc = Process(target=queue_size_monitor, args=(queue,))
  # queue_monitor_proc.start()

  with ProcessPoolExecutor(max_workers=NUM_PARALLEL) as executor:
    batch_size = 2_000 # 1_000
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
          # MAIN / ONLY SUCCESS CASE
          future.result()
          num_processed_this_run += 1
          print(f"✅ num processed this run: {num_processed_this_run}")
          # print_futures_stats(futures)
          # print(f"(while completing jobs) Current queue size: {queue.qsize()}")
          if num_processed_this_run % 100 == 0:
            print(f"🏎️ Num processed this run: {num_processed_this_run}. ⏰ Runtime: {(time.monotonic() - start_time_main_parallel):.2f} seconds")

          posthog.capture('llm-guided-ingest',
                event='success_ingest_running_total',
                properties={
                    'pdf-per-sec-running-total': float(num_processed_this_run/(time.monotonic() - start_time_main_parallel)),
                    'minio_path': f'{BUCKET_NAME}/{obj.object_name}'
                })

        except Exception as e:
          # MAIN / ONLY FAILURE CASE
          with open(ERR_LOG_FILE, 'a') as f:
            f.write(f"{obj.object_name} --- {str(e)}\n")
          posthog.capture('llm-guided-ingest',
                  event='failed_ingest',
                  properties={
                      'db_path': DB_PATH,
                      'minio_path': f'{BUCKET_NAME}/{obj.object_name}'
                  })
          print(f"Error processing {obj.object_name}: {str(e)}")
          traceback.print_exc()

      futures.clear()

  queue.put(None)
  db_proc.join()
  # queue_monitor_proc.terminate()

def upload_single_pdf(minio_object_name, queue):
  """
    This is the fundamental unit of parallelism: upload a single PDF to SQLite, all or nothing.
    """
  start_time_minio = time.monotonic()
  response = client.get_object(BUCKET_NAME, minio_object_name)
  file_content = response.read()
  response.close()
  response.release_conn()
  print(f"⏰ Minio download: {(time.monotonic() - start_time_minio):.2f} seconds")
  posthog.capture('llm-guided-ingest',
                  event='minio_download',
                  properties={
                      'runtime_sec': float(f"{(time.monotonic() - start_time_minio):.2f}"),
                      'minio_path': f'{BUCKET_NAME}/{minio_object_name}',
                      'grobid_using_GPU': False,
                  })

  with tempfile.NamedTemporaryFile() as tmp_file:
    tmp_file.write(file_content)
    tmp_file.flush()

    output_data = process_pdf_file(Path(tmp_file.name), BASE_TEMP_DIR, BASE_OUTPUT_DIR, f"{BUCKET_NAME}/{minio_object_name}", grobidClient)
    metadata, grouped_data, total_tokens, references, ref_num_tokens = parse_and_group_by_section(output_data)

    queue.put({
        'metadata': metadata,
        'total_tokens': total_tokens,
        'grouped_data': grouped_data,
        'references': references,
        'db_path': DB_PATH,
        'file_name': minio_object_name,
        'ref_num_tokens': ref_num_tokens,
        'minio_path': f'{BUCKET_NAME}/{minio_object_name}'
    })
  
  print(f"⭐️ Total ingest runtime: {(time.monotonic() - start_time_minio):.2f} seconds")
  posthog.capture('llm-guided-ingest',
                  event='success_ingest_v2',
                  properties={
                      'metadata': metadata,
                      'runtime_sec': float(f"{(time.monotonic() - start_time_minio):.2f}"),
                      'total_tokens': int(total_tokens),
                      'db_path': DB_PATH,
                      'minio_path': f'{BUCKET_NAME}/{minio_object_name}'
                  })

# Start <HELPER UTILS>
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
  while True:
    data = queue.get()
    if data is None:
      break
    try:
      insert_data(data['metadata'], data['total_tokens'], data['grouped_data'], data['db_path'], data['references'],
                  data['ref_num_tokens'], data['minio_path'])

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

# def queue_size_monitor(queue):
#   while True:
#     print(f"Current queue size: {queue.qsize()}")
#     time.sleep(10)


def print_futures_stats(futures):
  running_count = 0
  none_count = 0
  error_count = 0
  for f in futures:
    if f.running():
      running_count += 1
    elif f.done():
      if f.result() is None:
        none_count += 1
      elif f.exception() is not None:
        error_count += 1
  print(f"Batch progress. Running: {running_count}, Done: {none_count}, Errors: {error_count}")

# End </HELPER UTILS>

if __name__ == '__main__':
  main_parallel_upload()
