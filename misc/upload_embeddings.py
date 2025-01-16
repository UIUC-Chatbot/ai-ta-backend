# Iterate through, make embeddings, upload to Qdrant.

import concurrent.futures
import os
import time
import uuid

import pandas as pd
from dotenv import load_dotenv
from ollama import Client
from qdrant_client import QdrantClient, models
from qdrant_client.models import PointStruct
from tqdm import tqdm

load_dotenv()
full_start_time = time.monotonic()

ollama_client = Client(host=os.environ['OLLAMA_URL'])

qdrant_client = QdrantClient(url=os.environ['QDRANT_URL'],
                             port=int(os.environ['QDRANT_PORT']),
                             https=True,
                             api_key=os.environ['QDRANT_API_KEY'])

try:
  collection_info = qdrant_client.get_collection(collection_name=os.environ['QDRANT_COLLECTION_NAME'])
  print("Collection 'embedding' already exists.")
except Exception as e:
  print("Collection does not exist, creating a new one.")
  # Low memory usage w/ high precision (on disk).
  qdrant_client.create_collection(
      collection_name=os.environ['QDRANT_COLLECTION_NAME'],
      vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE, on_disk=True),
      hnsw_config=models.HnswConfigDiff(on_disk=True),
  )


def process_row(row_tuple):
  index, row = row_tuple
  try:
    result = ollama_client.embeddings(model='nomic-embed-text:v1.5', prompt=row['final_triplet_string'])

    payload = {
        'triplet': f"{row['x_name']} -- {row['relation']} -- {row['y_name']}",
        'triplet_string': row['final_triplet_string']
    }

    point = PointStruct(id=str(uuid.uuid4()), vector=result["embedding"], payload=payload)

    qdrant_client.upsert(collection_name=os.environ['QDRANT_COLLECTION_NAME'], points=[point])
    return True
  except Exception as e:
    print(f"Error processing row {index}: {str(e)}")
    return False


kg = pd.read_csv('kg_enriched_strings_minified_v2.csv', low_memory=False)

start_time = time.monotonic()
rows = list(kg.iterrows())
print(f"⏰ Runtime to list all the rows: {(time.monotonic() - start_time):.2f} seconds")

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
  results = list(tqdm(executor.map(process_row, rows), total=len(rows), desc="Processing rows"))

print(f"Successfully processed {sum(results)} out of {len(results)} rows")
print(f"⏰ Overall Runtime: {(time.monotonic() - full_start_time):.2f} seconds")
