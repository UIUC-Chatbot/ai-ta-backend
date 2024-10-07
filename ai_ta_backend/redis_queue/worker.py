# this script is used to start multiple workers for the redis queue
# it will be running on Kastan's server


from multiprocessing import Process
from rq import Worker, Queue, Connection
from redis import Redis

def start_worker():
    redis_conn = Redis()
    with Connection(redis_conn):
        worker = Worker([Queue()])
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
