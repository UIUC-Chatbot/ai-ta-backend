from ai_ta_backend.service.ingest_service import IngestService


def ingest_wrapper(inputs):
  print("Running ingest_wrapper")
  ingester = IngestService()
  print(f"Inputs in wrapper: {inputs}")
  return ingester.main_ingest(**inputs)
