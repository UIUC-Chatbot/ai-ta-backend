import os
import json

from redis import Redis
from rq import Queue
from rq.job import Job
from rq.worker import Worker
from rq.exceptions import NoSuchJobError
from dotenv import load_dotenv
import traceback as tb

from typing import Optional
from injector import inject

from ai_ta_backend.utils.task import ingest_wrapper
from ai_ta_backend.database.sql import SQLAlchemyDatabase
from ai_ta_backend.service.posthog_service import PosthogService
from ai_ta_backend.service.sentry_service import SentryService

class QueueService:
    """
    Contains all methods for business logic of the queue service.
    """
    @inject
    def __init__(self, sqlDb: SQLAlchemyDatabase, posthog: Optional[PosthogService], sentry: Optional[SentryService]):
        self.sqlDb = sqlDb
        self.sentry = sentry
        self.posthog = posthog

        self.redis_conn = Redis(port=int(os.environ["INGEST_REDIS_PORT"]),
                               host=os.environ["INGEST_REDIS_URL"],
                               password=os.environ["INGEST_REDIS_PASSWORD"],
                               socket_timeout=None,
                               )
        
        self.task_queue = Queue(connection=self.redis_conn)
    
    def queue_ingest_task(self, inputs):
        """
        Queue an ingest task.
        """
        try:
            print(f"Queueing ingest task for {input}")

            job = self.task_queue.enqueue(ingest_wrapper, inputs, on_success=self.update_ingest_success, on_failure=self.update_ingest_failure)
            print(f"Job {job.id} enqueued, status: {job.get_status()}")

            # Insert into 'documents_in_progress'
            doc_progress_payload = {
                "s3_path": inputs['s3_paths'][0],
                "readable_filename": inputs['readable_filename'],
                "course_name": inputs['course_name'],
                "beam_task_id": job.id,
            }
            print("doc_progress_payload: ", doc_progress_payload)

            self.sqlDb.insertDocsInProgress(doc_progress_payload)
            
            return job.id
        except Exception as e:
            print(f"Error queueing ingest task: {str(e)}")
            if self.sentry:
                self.sentry.capture_exception(e)
            return None
        
    def update_ingest_success(self, job, result):
        """
        Update the status of ingest after successful execution.
        """
        try:
            print("Updating task success...")
            result_json = json.loads(result)
            if result_json['failure_ingest']:
                # call the failure update function here in case task status is success, but ingest has failed :(
                self.update_ingest_failure(job, Exception, Exception(result_json["failure_ingest"]), None)
            else:
                # remove from 'documents_in_progress'
                self.sqlDb.deleteDocsInProgress(job.id)
                print(f"Job {job.id} completed successfully!")
        except Exception as e:
            print(f"Error updating status for job {job.id}: {str(e)}")
            if self.sentry:
                self.sentry.capture_exception(e)
    
    def update_ingest_failure(self, job, exc_type, exc_value, traceback):
        """
        Update the status of ingest after failed execution.
        """
        try:
            print("Updating task failure...")
            error_message = f"{exc_type.__name__}: {str(exc_value)}"
            full_traceback = ''.join(tb.format_tb(traceback))
            combined_message = f"{error_message}\nTraceback:\n{full_traceback}"

            # Insert into 'documents_failed'
            failure_payload = {
                "s3_path": job.args[0]['s3_paths'][0],
                "readable_filename": job.args[0]['readable_filename'],
                "course_name": job.args[0]['course_name'],
                "error": combined_message
            }
            self.sqlDb.insertDocsFailed(failure_payload)

            # Remove from 'documents_in_progress'
            self.sqlDb.deleteDocsInProgress(job.id)
            print(f"Job {job.id} failed!")

        except Exception as e:
            print(f"Error updating status for job {job.id}: {str(e)}")
            if self.sentry:
                self.sentry.capture_exception(e)