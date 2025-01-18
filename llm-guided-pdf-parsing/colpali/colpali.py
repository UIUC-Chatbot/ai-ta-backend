import requests
from tqdm import tqdm
import os
from minio import Minio
from pdf_to_images import pdf_to_images
from qdrant_client import QdrantClient
from qdrant_client.http import models
import stamina
from dotenv import load_dotenv

load_dotenv()

BUCKET_NAME = 'pubmed2'
FLASK_API_URL = 'http://localhost:5000/process_image'

minio_client = Minio(
    os.environ['MINIO_API_ENDPOINT'],
    access_key=os.environ['MINIO_ACCESS_KEY'],
    secret_key=os.environ['MINIO_SECRET_KEY'],
    secure=False,
)

qdrant_client = QdrantClient(
    url=os.environ['QDRANT_URL'],
    port=os.environ['QDRANT_PORT'],
    https=True,
    api_key=os.environ['QDRANT_API_KEY']
)

collection_name = "colpali"
vector_size = 128
qdrant_client.recreate_collection(
    collection_name=collection_name,
    on_disk_payload=True,
    optimizers_config=models.OptimizersConfigDiff(indexing_threshold=100),
    vectors_config=models.VectorParams(
        size=vector_size,
        distance=models.Distance.COSINE,
        multivector_config=models.MultiVectorConfig(comparator=models.MultiVectorComparator.MAX_SIM),
        quantization_config=models.ScalarQuantization(
            scalar=models.ScalarQuantizationConfig(type=models.ScalarType.INT8, quantile=0.99, always_ram=True),
        ),
    ),
)

output_dir = "output_images"
os.makedirs(output_dir, exist_ok=True)

@stamina.retry(on=Exception, attempts=3)
def upsert_to_qdrant(points):
    try:
        qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
            wait=False,
        )
    except Exception as e:
        print(f"Error during upsert: {e}")
        return False
    return True

# Process the first 1000 files from the MinIO bucket
objects = minio_client.list_objects(BUCKET_NAME, recursive=True)

processed_files = 0
point_id = 0
with tqdm(total=1000, desc="Processing Files") as pbar:
    for obj in objects:
        if processed_files >= 1000:
            break

        local_file_path = obj.object_name
        local_save_path = os.path.join(output_dir, os.path.basename(local_file_path))

        minio_client.fget_object(BUCKET_NAME, obj.object_name, local_save_path)

        pdf_to_images(local_save_path, output_dir)

        for image_name in os.listdir(output_dir):
            if not image_name.endswith((".png", ".jpg", ".jpeg")):
                continue

            image_path = os.path.join(output_dir, image_name)

            try:
                with open(image_path, 'rb') as f:
                    files = {'file': (image_name, f)}
                    response = requests.post(FLASK_API_URL, files=files)
                
                if response.status_code == 200:
                    image_embedding = response.json().get('embedding')
                else:
                    print(f"Error processing image {image_name}: {response.json().get('error')}")
                    continue

                multivector = image_embedding
                point = models.PointStruct(
                    id=point_id,
                    vector=multivector,
                    payload={
                        "source": "minio bucket",
                        "file_name": os.path.basename(image_path),
                        "original_file": local_file_path,
                    },
                )

                upsert_to_qdrant([point])
                print(f"Successfully inserted: {image_name}")
                point_id += 1

            except Exception as e:
                print(f"Error uploading image {image_name} to Flask API: {e}")
                continue

            os.remove(image_path)

        processed_files += 1
        pbar.update(1)

print("Processing complete!")
