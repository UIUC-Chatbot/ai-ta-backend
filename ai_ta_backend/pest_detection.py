# from typing import List
# from PIL import Image
# from ultralytics import YOLO
# from pathlib import Path

# class PestDetection:
#   """
#     AIFARMS CropWizard Plugin for Pest Detection and Classification
#     """

#   def __init__(self):
#     # Load a custom trained YOLOv8n model for pest detection and classification By Aditya Sengupta
#     # Google Colab Implementation:
#     # https://colab.research.google.com/drive/1GO-lw2PJtVewlA-xhBfgBLId8v4v-BE2?usp=sharing

#     # The model weights can be found at:
#     # https://www.dropbox.com/scl/fi/xf8wi0jy72kuk3xl47dnx/Aditya-Pest-Detection-YOLO-V1.pt
#     self.model = YOLO(Path.cwd() / 'ai_ta_backend/pest_detection_model_weights.pt')

#   def detect_pests(self, image_paths: List[str]) -> List[Image.Image]:
#     # Run inference
#     results = self.model(image_paths)  # results object with inference results

#     annotated_images = []

#     # Extract annotated images from the results object
#     # Flatten the results object to get the annotated images for each input image
#     for result_set in results:
#       for r in result_set:
#         im_array = r.plot()  # plot a BGR numpy array of predictions
#         im = Image.fromarray(im_array[..., ::-1])  # RGB PIL image (annotated with bounding boxes and class labels)
#         annotated_images.append(im)

#     return annotated_images

# if __name__ == '__main__':
#   # Sample usage with multiple images
#   plugin = PestDetection()
#   image_urls = [
#       'https://www.arborday.org/trees/health/pests/images/figure-whiteflies-1.jpg',
#       'https://www.arborday.org/trees/health/pests/images/figure-japanese-beetle-3.jpg'
#   ]
#   output = plugin.detect_pests(image_urls)

#   # Print annotated images
#   for image in output:
#     image.show()
