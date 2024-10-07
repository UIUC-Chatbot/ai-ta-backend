# main_script.py
from rq import Queue
from redis import Redis
from task import background_task  # Correct import path

redis_conn = Redis()
task_queue = Queue(connection=redis_conn)

# Add the task to the queue with a duration of 5 seconds
job = task_queue.enqueue(background_task, 10)

print(f"Job {job.id} enqueued, status: {job.get_status()}")

job2 = task_queue.enqueue(background_task, 5)

print(f"Job {job2.id} enqueued, status: {job2.get_status()}")
