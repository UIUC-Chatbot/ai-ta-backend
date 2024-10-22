import time
from ai_ta_backend.redis_queue.ingest import Ingest

def ingest_wrapper(inputs):
  print("Running ingest_wrapper")
  ingester = Ingest()
  print(f"Inputs in wrapper: {inputs}")
  return ingester.main_ingest(**inputs)
