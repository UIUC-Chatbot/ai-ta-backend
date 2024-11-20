# this script is used to start multiple workers for the redis queue
# it will be running on Kastan's server
import logging
import os
import sys
from multiprocessing import Process
import signal
import sys

from redis import Redis
from rq import Connection, Queue, Worker
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')#logging.basicConfig(level=logging.DEBUG)

# For some crazy reason, all 3 of these below lines are needed to get imports working.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(project_root)
from ai_ta_backend.redis_queue.task import ingest_wrapper

# ensure a clean shutdown in Docker
def signal_handler(sig, frame):
    print("Shutting down gracefully...")
    # Terminate all child processes
    workers = Worker.all(redis)
    for worker in workers:
        send_shutdown_command(redis, worker.name)
    sys.exit(0)

def start_worker():
    logging.info("Starting Redis worker...")
    redis_conn = Redis(port=int(os.environ["INGEST_REDIS_PORT"]),
                      host=os.environ["INGEST_REDIS_HOST"],
                      password=os.environ["INGEST_REDIS_PASSWORD"],
                      socket_timeout=None)

    with Connection(redis_conn):
        worker = Worker([Queue("default")])
        worker.work()

if __name__ == "__main__":
    workers = []  # Move this to global scope
    worker_count = os.cpu_count() or 4

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Start multiple worker processes
    for _ in range(worker_count):
        p = Process(target=start_worker)
        p.start()
        workers.append(p)

    # Wait for all workers to complete
    try:
        for worker in workers:
            worker.join()
    except KeyboardInterrupt:
        print("Caught KeyboardInterrupt, shutting down workers...")
        for worker in workers:
            worker.terminate()
            worker.join()
