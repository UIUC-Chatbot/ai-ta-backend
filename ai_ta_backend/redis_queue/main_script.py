import os
from redis import Redis
from rq import Queue
from rq.job import Job
from rq.worker import Worker
from rq.exceptions import NoSuchJobError
from dotenv import load_dotenv
import traceback as tb
import json
from ai_ta_backend.redis_queue.task import ingest_wrapper
from ai_ta_backend.redis_queue.sql_alchemy import SQLAlchemyIngestDB
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


load_dotenv()

# Initialize connections
# redis_conn = Redis(port=int(os.environ["INGEST_REDIS_PORT"]),
#                    host=os.environ["INGEST_REDIS_URL"],
#                    password=os.environ["INGEST_REDIS_PASSWORD"],
#                    socket_timeout=None,
#                    )

redis_conn = Redis(port=6379,
                     host="redis",
                     socket_timeout=None,
                     )

task_queue = Queue(connection=redis_conn)

sql_session = SQLAlchemyIngestDB()

# Callback function to update the status after execution
def update_task_status(job, connection, result, *args, **kwargs):
    print("IN UPDATE TASK STATUS")
    try:
        job_id = job.id
        print(result)
        result_json = json.loads(result)
        if result_json['failure_ingest']:
            # call the failure update func here in case task status is success, but ingest has failed :(
            update_task_failure(job, Exception, Exception(result_json["failure_ingest"]), None)
        else:
            # remove from 'documents_in_progress'
            sql_session.delete_document_in_progress(job_id)
            print(f"Job {job_id} completed successfully!")
    except Exception as e:
        print(f"Error updating status for job {job.id}: {str(e)}")

def update_task_failure(job, exc_type, exc_value, traceback):
    print("IN UPDATE TASK FAILURE")
    try:
        job_id = job.id
        error_message = f"{exc_type.__name__}: {str(exc_value)}"
        full_traceback = ''.join(tb.format_tb(traceback))
        combined_message = f"{error_message}\nTraceback:\n{full_traceback}"
        print("JOB ARGS: ", job.args)
        
        # Update status to 'failed'
        failure_payload = {
            "s3_path": job.args[0]['s3_paths'][0],
            "readable_filename": job.args[0]['readable_filename'],
            "course_name": job.args[0]['course_name'],
            "error": combined_message
        }
        sql_session.insert_failed_document(failure_payload)

        # Remove from 'documents_in_progress'
        sql_session.delete_document_in_progress(job_id)

        print(f"Job {job_id} failed!")
    except Exception as e:
        print(f"Error updating status for job {job_id}: {str(e)}")


def queue_ingest_task(inputs):
    logging.info(f"Queueing ingest task for {inputs['course_name']}")
    logging.info("Inputs: ", inputs)

    response = redis_conn.ping()
    if response:
        logging.info("Redis server is online")
    else:
        logging.info("Redis is offline")

    job = task_queue.enqueue(ingest_wrapper, inputs, on_success=update_task_status, on_failure=update_task_failure)
    logging.info(f"Job {job.id} enqueued, status: {job.get_status()}")

    # Insert into 'documents_in_progress'
    doc_progress_payload = {
        "s3_path": inputs['s3_paths'][0],
        "readable_filename": inputs['readable_filename'],
        "course_name": inputs['course_name'],
        "beam_task_id": job.id,
    }
    print("doc_progress_payload: ", doc_progress_payload)
    sql_session.insert_document_in_progress(doc_progress_payload)

    return job.id
