# tasks.py

import time
from ai_ta_backend.redis_queue.ingest import Ingest


def background_task(duration):
  """Simulates a long-running task."""
  print(f"Task started, will take {duration} seconds.")
  time.sleep(duration)
  print("Task completed!")
  return "Done"


def ingest_wrapper(inputs):
  print("Running ingest_wrapper")
  ingester = Ingest()
  print(f"Inputs in wrapper: {inputs}")
  return ingester.main_ingest(**inputs)
