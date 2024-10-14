# this script is used to start multiple workers for the redis queue
# it will be running on Kastan's server
import logging
import os
import sys
from multiprocessing import Process

from redis import Redis
from rq import Connection, Queue, Worker

logging.basicConfig(level=logging.INFO)

# sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(project_root)

from ai_ta_backend.redis_queue.task import ingest_wrapper  # Add this import


def start_worker():
  logging.info("Starting Redis worker...")
  redis_conn = Redis(host='localhost', port=6379, db=0)
  with Connection(redis_conn):
    worker = Worker([Queue("default")])
    worker.work()


if __name__ == "__main__":
  worker_count = 4  # Number of workers you want to start
  workers = []

  # Start multiple worker processes
  for _ in range(worker_count):
    p = Process(target=start_worker)
    p.start()
    workers.append(p)

  # Wait for all workers to complete (optional)
  for worker in workers:
    worker.join()
