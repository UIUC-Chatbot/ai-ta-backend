"""
Run with: $ modal serve ai_ta_backend/modal/pest_detection.py
Deploy with with: $ modal deploy ai_ta_backend/modal/pest_detection.py

Just send a post request here: https://kastanday--v2-pest-detection-yolo-model-predict.modal.run/
with body: 
{
    "image_urls": [
        "https://www.arborday.org/trees/health/pests/images/figure-whiteflies-1.jpg",
        "https://www.arborday.org/trees/health/pests/images/figure-japanese-beetle-3.jpg"
    ]
}

Inspired by https://modal.com/docs/examples/webcam#prediction-function
"""
import inspect
import json
import os
from tempfile import NamedTemporaryFile
import traceback
from typing import List
import uuid

from fastapi import Request
import modal
from modal import build
from modal import enter
from modal import Secret
from modal import Stub
from modal import web_endpoint

# Simpler image, but slower cold starts: modal.Image.from_registry('ultralytics/ultralytics:latest-cpu')
image = (
    modal.Image.debian_slim(python_version="3.10").apt_install("libgl1-mesa-glx", "libglib2.0-0")
    # .run_commands(["apt-get install -y libgl1-mesa-glx libglib2.0-0 wget"])
    .pip_install(
        "opencv-python",
        "torch==2.2.0",
        "ultralytics==8.1.0",
        "torchvision==0.17.0",
        "boto3==1.28.79",
        "fastapi==0.109.2",
        "pillow",
    ))
stub = Stub("v2_pest_detection_yolo", image=image)

# Imports needed inside the image
with image.imports():

  import boto3
  from PIL import Image
  import requests
  from ultralytics import YOLO


@stub.cls(cpu=1, image=image, secrets=[Secret.from_name("uiuc-chat-aws")])
class Model:
  """
  1. Build (bake things into the image for faster subsequent startups)
  2. Enter (run once per container start)
  3. Web Endpoint (serve a web endpoint)
  """

  @build()
  def download_model(self):
    """Model weights are downloaded once at image build time using the @build hook and saved into the image. 'Baking' models into the modal.Image at build time provided the fastest cold start. """
    model_url = "https://assets.kastan.ai/pest_detection_model_weights.pt"
    response = requests.get(model_url)

    model_path = "/cache/pest_detection_model_weights.pt"
    os.makedirs("/cache/", exist_ok=True)
    with open(model_path, 'wb') as f:
      f.write(response.content)

  @enter()
  def run_this_on_container_startup(self):
    """Runs once per container start. Like __init__ but for the container."""
    self.model = YOLO('/cache/pest_detection_model_weights.pt')
    self.s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    )

  @web_endpoint(method="POST")
  async def predict(self, request: Request):
    """
    This used to use the method decorator
    Run the pest detection plugin on an image.
    """
    print("Inside predict() endpoint")

    input = await request.json()
    print("Request.json(): ", input)
    image_urls = input.get('image_urls', [])

    if image_urls and isinstance(image_urls, str):
      image_urls = json.loads(image_urls)
    print(f"Final image URLs: {image_urls}")

    try:
      # Run the plugin
      annotated_images = self._detect_pests(image_urls)
      print(f"annotated_images found: {len(annotated_images)}")
      results = []
      # Generate a unique ID for the request
      unique_id = uuid.uuid4()
      # self.posthog.capture('distinct_id_of_the_user',
      #                      event='run_pest_detection_invoked',
      #                      properties={
      #                          'image_urls': image_urls,
      #                          'unique_id': unique_id,
      #                      })
      for index, image in enumerate(annotated_images):
        # Infer the file extension from the image URL or set a default
        file_extension = '.png'
        image_format = file_extension[1:].upper()

        with NamedTemporaryFile(mode='wb', suffix=file_extension) as tmpfile:
          # Save the image with the specified format
          image.save(tmpfile, format=image_format)
          tmpfile.flush()  # Ensure all data is written to the file
          tmpfile.seek(0)  # Move the file pointer to the start of the file
          # Include UUID and index in the s3_path
          s3_path = f'pest_detection/annotated-{unique_id}-{index}{file_extension}'
          # Upload the file to S3
          with open(tmpfile.name, 'rb') as file_data:
            self.s3_client.upload_fileobj(Fileobj=file_data, Bucket=os.getenv('S3_BUCKET_NAME'), Key=s3_path)
          results.append(s3_path)
      return results
    except Exception as e:
      err = f"❌❌ Error in (pest_detection): `{inspect.currentframe().f_code.co_name}`: {e}\nTraceback:\n{traceback.format_exc()}"  # type: ignore
      print(err)
      # sentry_sdk.capture_exception(e)
      return err

  def _detect_pests(self, image_paths: List[str]) -> List[Image.Image]:
    """ Run pest detection on the given images. """
    # Run inference
    results = self.model(image_paths)  # results object with inference results

    annotated_images = []

    # Extract annotated images from the results object
    # Flatten the results object to get the annotated images for each input image
    for result_set in results:
      for r in result_set:
        im_array = r.plot()  # plot a BGR numpy array of predictions
        im = Image.fromarray(im_array[..., ::-1])  # RGB PIL image (annotated with bounding boxes and class labels)
        annotated_images.append(im)
    return annotated_images
