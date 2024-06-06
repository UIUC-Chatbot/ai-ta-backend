"""
To deploy: beam deploy pest_detection.py
For testing: beam serve pest_detection.py
Use CAII gmail to auth.
"""
import inspect
import io
import json
import os
import time
import traceback
from typing import Any, Dict, List

import beam
import requests
from beam import App, QueueDepthAutoscaler, Runtime, Volume
from PIL import Image
from ultralytics import YOLO

# Simpler image, but slower cold starts: beam.Image.from_registry('ultralytics/ultralytics:latest-cpu')

requirements = [
    "torch==2.2.0",
    "ultralytics==8.1.0",
    "torchvision==0.17.0",
    "opencv-python",
    "pillow",
]

volume_path = "./models"

app = App(
    "pest_detection",
    runtime=Runtime(
        cpu=1,
        memory="3Gi",
        image=beam.Image(  # type: ignore
            python_version="python3.10",
            python_packages=requirements,
            # commands=["apt-get update && apt-get install -y ffmpeg tesseract-ocr"],
        ),
    ),
    volumes=[Volume(
        name="my_models",
        path=volume_path,
    )],
)


def loader():
  """Model weights are downloaded once at image build time using the @build hook and saved into the image. 'Baking' models into the modal.Image at build time provided the fastest cold start. """
  model_url = "https://assets.kastan.ai/pest_detection_model_weights.pt"
  model_path = f'{volume_path}/pest_detection_model_weights.pt'
  start_time = time.monotonic()

  # save/load model to/from volume
  if not os.path.exists(model_path):
    print("Downloading model from the internet")
    response = requests.get(model_url, timeout=60)
    with open(model_path, "wb") as f:
      f.write(response.content)
    model = YOLO(response.content)
  else:
    print("Loading model from volume")
    model = YOLO(model_path)

  print(f"⏰ Runtime to load model: {(time.monotonic() - start_time):.2f} seconds")
  return model


# autoscaler = QueueDepthAutoscaler(max_tasks_per_replica=2, max_replicas=3)
@app.rest_api(
    workers=1,
    max_pending_tasks=10,
    max_retries=1,
    timeout=60,
    keep_warm_seconds=60 * 3,
    # autoscaler=autoscaler
    loader=loader)
def predict(**inputs: Dict[str, Any]):
  """
    Run the pest detection plugin on an image and return image data as blobs.
    """
  print("Inside predict() endpoint")
  model = inputs["context"]
  image_urls: List[str] = inputs.get('image_urls', [])  # type: ignore
  print(f"Image URLs: {image_urls}")

  if image_urls and isinstance(image_urls, str):
    image_urls = json.loads(image_urls)
  print(f"Final image URLs: {image_urls}")

  if not image_urls:
    return "❌ No input image URLs provided."

  try:
    # Run the plugin
    annotated_images = _detect_pests(model, image_urls)
    print(f"annotated_images found: {len(annotated_images)}")
    blob_results = []

    for image in annotated_images:
      # Convert image to bytes
      img_byte_arr = io.BytesIO()
      image.save(img_byte_arr, format='PNG')
      img_byte_arr = img_byte_arr.getvalue()
      blob_results.append(img_byte_arr)

    return blob_results
  except Exception as e:
    err = f"❌❌ Error in (pest_detection): `{inspect.currentframe().f_code.co_name}`: {e}\nTraceback:\n{traceback.format_exc()}"  # type: ignore
    print(err)
    # sentry_sdk.capture_exception(e)
    return err


def _detect_pests(model, image_paths: List[str]) -> List[Image.Image]:
  """ Run pest detection on the given images. """
  # Run inference
  results = model(image_paths)  # results object with inference results

  annotated_images = []

  # Extract annotated images from the results object
  # Flatten the results object to get the annotated images for each input image
  for result_set in results:
    for r in result_set:
      im_array = r.plot()  # plot a BGR numpy array of predictions
      im = Image.fromarray(im_array[..., ::-1])  # RGB PIL image (annotated with bounding boxes and class labels)
      annotated_images.append(im)
  return annotated_images
