# this script is used to start multiple workers for the redis queue
# it will be running on Kastan's server
import logging
import os
import sys
from multiprocessing import Process

from redis import Redis
from rq import Connection, Queue, Worker
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')#logging.basicConfig(level=logging.DEBUG)

# sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# For some crazy reason, all 3 of these below lines are needed to get imports working.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(project_root)
from ai_ta_backend.redis_queue.task import ingest_wrapper  # Add this import


def start_worker():
  logging.info("Starting Redis worker...")
  # redis_conn = Redis(port=int(os.environ["INGEST_REDIS_PORT"]),
  #                    host=os.environ["INGEST_REDIS_URL"],
  #                    password=os.environ["INGEST_REDIS_PASSWORD"],
  #                    socket_timeout=None,
  #                    )
  redis_conn = Redis(port=6379,
                     host="redis",
                     socket_timeout=None,
                     )

  with Connection(redis_conn):
    worker = Worker([Queue("default")])
    worker.work()


if __name__ == "__main__":
  worker_count = os.cpu_count() or 4 # Dynamically set worker count based on CPU cores
  workers = []

  # Start multiple worker processes
  for _ in range(worker_count):
    p = Process(target=start_worker)
    p.start()
    workers.append(p)

  # Wait for all workers to complete (optional)
  for worker in workers:
    worker.join()
