# this script is used to start multiple workers for the redis queue
# it will be running on Kastan's server
import sys
import os
from multiprocessing import Process
from rq import Worker, Queue, Connection
from redis import Redis

import logging
logging.basicConfig(level=logging.INFO)

sys.path.append(os.path.abspath(os.path.dirname(__file__)))


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
