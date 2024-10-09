# main_script.py --- this sends the task to the queue
# after calling the ingest API, the ingest function can be called here and the task can be sent to the queue
from rq import Queue
from redis import Redis
from task import background_task, ingest_wrapper  # Correct import path

redis_conn = Redis()
task_queue = Queue(connection=redis_conn)

# Add the task to the queue with a duration of 5 seconds
job = task_queue.enqueue(background_task, 10)

print(f"Job {job.id} enqueued, status: {job.get_status()}")

job2 = task_queue.enqueue(background_task, 5)

print(f"Job {job2.id} enqueued, status: {job2.get_status()}")

inputs = {
    "course_name": "asmita",
    "url": "www.abc.com",
    "base_url": "",
    "s3_path": ["s3://abc.com"],
    "readable_filename": "abc",
    "doc_groups": ['abc', 'def'],
}

job3 = task_queue.enqueue(ingest_wrapper, inputs)
print(f"Job {job3.id} enqueued, status: {job3.get_status()}")
