# tasks.py

import time
from ingest import Ingest


def background_task(duration):
    """Simulates a long-running task."""
    print(f"Task started, will take {duration} seconds.")
    time.sleep(duration)
    print("Task completed!")
    return "Done"


def ingest_wrapper(inputs):
    ingester = Ingest()
    return ingester.main_ingest(**inputs)