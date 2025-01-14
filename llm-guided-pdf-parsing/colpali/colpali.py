from qdrant_client import QdrantClient
from dotenv import load_dotenv
import stamina
from minio import Minio
from pdf_to_images import pdf_to_images
from qdrant_client.http import models
import os
import torch
from PIL import Image
from colpali_engine.models import ColQwen2, ColQwen2Processor
from tqdm import tqdm

import concurrent.futures
import threading
from queue import Queue

load_dotenv()
BUCKET_NAME = 'pubmed2'

minio_client = Minio(
    os.environ['MINIO_API_ENDPOINT'],
    access_key=os.environ['MINIO_ACCESS_KEY'],
    secret_key=os.environ['MINIO_SECRET_KEY'],
    secure=False,
)

# Initialize Qdrant client
qdrant_client = QdrantClient(
    url=os.environ['QDRANT_URL'],
    port=os.environ['QDRANT_PORT'],
    https=True,
    api_key=os.environ['QDRANT_API_KEY']
)

collection_name = "colpali"
vector_size = 128

# Configure Qdrant collection
qdrant_client.recreate_collection(
    collection_name=collection_name,
    on_disk_payload=True,
    optimizers_config=models.OptimizersConfigDiff(
        indexing_threshold=100
    ),
    vectors_config=models.VectorParams(
        size=vector_size,
        distance=models.Distance.COSINE,
        multivector_config=models.MultiVectorConfig(
            comparator=models.MultiVectorComparator.MAX_SIM
        ),
        quantization_config=models.ScalarQuantization(
            scalar=models.ScalarQuantizationConfig(
                type=models.ScalarType.INT8,
                quantile=0.99,
                always_ram=True,
            ),
        ),
    ),
)

colpali_model = ColQwen2.from_pretrained(
    "vidore/colqwen2-v1.0",
    device_map="cpu",
).eval()
colpali_processor = ColQwen2Processor.from_pretrained("vidore/colqwen2-v1.0")

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

processed_files = 0  # Counter for processed files
point_id = 0
with tqdm(total=1000, desc="Processing Files") as pbar:
    for obj in objects:
        if processed_files >= 1000:
            break  # Stop after processing 1000 files

        local_file_path = obj.object_name
        local_save_path = os.path.join(output_dir, os.path.basename(local_file_path))

        # Download the file
        minio_client.fget_object(BUCKET_NAME, obj.object_name, local_save_path)

        # Convert PDF to images and store in the output directory
        pdf_to_images(local_save_path, output_dir)

        # Process extracted images one by one
        for image_name in os.listdir(output_dir):
            if not image_name.endswith((".png", ".jpg", ".jpeg")):
                continue  # Skip non-image files

            image_path = os.path.join(output_dir, image_name)

            # Load image
            image = Image.open(image_path)

            # Process and encode image
            with torch.no_grad():
                processed_image = colpali_processor.process_images([image]).to(colpali_model.device)
                image_embedding = colpali_model(**processed_image)[0]  # First (and only) embedding

            # Prepare the point for Qdrant
            multivector = image_embedding.cpu().float().numpy().tolist()
            point = models.PointStruct(
                id=point_id,  # Unique ID for each file
                vector=multivector,
                payload={
                    "source": "minio bucket",
                    "file_name": os.path.basename(image_path),
                    "original_file": local_file_path,
                },
            )

            # Upload point to Qdrant
            try:
                upsert_to_qdrant([point])
                print(f"Successfully inserted: {image_name}")
                point_id+=1
            except Exception as e:
                print(f"Error during upsert: {e}")
                continue

            # Delete processed image to free space
            os.remove(image_path)

        # Update progress
        processed_files += 1
        pbar.update(1)

print("Processing complete!")
# batch_size = 4  # Process multiple images in a batch
# thread_lock = threading.Lock()  # Lock for thread-safe printing


# def process_image_batch(image_paths, point_id_start, local_file_path):
#     points = []
#     try:
#         # Load and process images
#         images = [Image.open(path) for path in image_paths]

#         # Preprocess and encode batch
#         with torch.no_grad():
#             batch_images = colpali_processor.process_images(images).to(colpali_model.device)
#             batch_embeddings = colpali_model(**batch_images)

#         # Prepare points
#         for idx, embedding in enumerate(batch_embeddings):
#             multivector = embedding.cpu().float().numpy().tolist()
#             point = models.PointStruct(
#                 id=point_id_start + idx,
#                 vector=multivector,
#                 payload={
#                     "source": "minio bucket",
#                     "file_name": os.path.basename(image_paths[idx]),
#                     "original_file": local_file_path,
#                 },
#             )
#             points.append(point)

#         # Upsert to Qdrant
#         if upsert_to_qdrant(points):
#             with thread_lock:
#                 for path in image_paths:
#                     print(f"Successfully inserted: {os.path.basename(path)}")
#         return len(points)
#     except Exception as e:
#         with thread_lock:
#             print(f"Error processing batch: {e}")
#         return 0


# # Thread-safe PDF to image converter
# def pdf_to_images_thread_safe(local_save_path):
#     with thread_lock:
#         pdf_to_images(local_save_path, output_dir)


# # Process files in the MinIO bucket
# processed_files = 0
# point_id = 0

# with tqdm(total=1000, desc="Processing Files") as pbar:
#     with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
#         for obj in objects:
#             if processed_files >= 1000:
#                 break

#             local_file_path = obj.object_name
#             local_save_path = os.path.join(output_dir, os.path.basename(local_file_path))

#             # Download file
#             minio_client.fget_object(BUCKET_NAME, obj.object_name, local_save_path)

#             # Convert PDF to images
#             executor.submit(pdf_to_images_thread_safe, local_save_path).result()

#             # Gather images
#             image_paths = [
#                 os.path.join(output_dir, fname)
#                 for fname in os.listdir(output_dir)
#                 if fname.endswith((".png", ".jpg", ".jpeg"))
#             ]

#             # Process in batches
#             for i in range(0, len(image_paths), batch_size):
#                 batch_paths = image_paths[i:i + batch_size]
#                 processed_count = process_image_batch(batch_paths, point_id, local_file_path)
#                 point_id += processed_count

#                 # Delete processed images
#                 for path in batch_paths:
#                     os.remove(path)

#             processed_files += 1
#             pbar.update(1)

# print("Processing complete!")