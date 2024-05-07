"""
To deploy: beam deploy canvas_ingest.py --profile caii-ncsa
Use CAII gmail to auth.
"""

import os
import shutil
import re
import json
import uuid
from typing import Any, Callable, Dict, List, Optional, Union

import boto3
from posthog import Posthog
import requests
from canvasapi import Canvas
import beam
from beam import App, QueueDepthAutoscaler, Runtime  # RequestLatencyAutoscaler,

requirements = [
  "boto3==1.28.79",
  "posthog==3.1.0",
  "canvasapi==3.2.0",
]

app = App("canvas_ingest",
          runtime=Runtime(
              cpu=1,
              memory="2Gi",
              image=beam.Image(
                  python_version="python3.10",
                  python_packages=requirements,
                  # commands=["apt-get update && apt-get install -y ffmpeg tesseract-ocr"],
              ),
          ))


def loader():
  """
  The loader function will run once for each worker that starts up. https://docs.beam.cloud/deployment/loaders
  """

  # S3
  s3_client = boto3.client(
      's3',
      aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
  )
  canvas_client = Canvas("https://canvas.illinois.edu", os.getenv('CANVAS_ACCESS_TOKEN'))

  posthog = Posthog(sync_mode=True, project_api_key=os.environ['POSTHOG_API_KEY'], host='https://app.posthog.com')
  # sentry_sdk.init(
  #     dsn="https://examplePublicKey@o0.ingest.sentry.io/0",
  #     enable_tracing=True,
  # )
  
  return s3_client, canvas_client, posthog


autoscaler = QueueDepthAutoscaler(max_tasks_per_replica=2, max_replicas=3)

@app.task_queue(
    workers=1,
    # callback_url is used for 'in progress' & 'failed' tracking. But already handeled by other Beam endpoint.
    # callback_url='https://uiuc-chat-git-ingestprogresstracking-kastanday.vercel.app/api/UIUC-api/ingestTaskCallback',
    max_pending_tasks=15_000,
    max_retries=3,
    timeout=-1,
    loader=loader,
    autoscaler=autoscaler)
def canvas_ingest(**inputs: Dict[str, Any]):
  s3_client, canvas_client, posthog = inputs["context"]


  course_name: List[str] | str = inputs.get('course_name', '')
  canvas_url: List[str] | str | None = inputs.get('canvas_url', None)
  print(f"{course_name}=")
  print(f"{canvas_url}=")
  
  # canvas.illinois.edu/courses/COURSE_CODE
  match = re.search(r'canvas\.illinois\.edu/courses/([^/]+)', canvas_url)
  canvas_course_id = match.group(1) if match else None

  ingester = CanvasIngest(s3_client, canvas_client, posthog)
  ingester.ingest_course_content(canvas_course_id, course_name)

  # Can get names, but not emails. e.g. Collected names:  ['UIUC Course AI', 'Shannon Bradley', 'Asmita Vijay Dabholkar', 'Kastan Day', 'Volodymyr Kindratenko', 'Max Lindsey', 'Rohan Marwaha', 'Joshua Min', 'Neha Sheth', 'George Tamas']
  # ingester.add_users(canvas_course_id, course_name)


class CanvasIngest():

  def __init__(self, s3_client, canvas_client, posthog):
    self.posthog = posthog
    self.s3_client = s3_client
    self.canvas_client = canvas_client
    self.headers = {"Authorization": "Bearer " + os.getenv('CANVAS_ACCESS_TOKEN')}

  def upload_file(self, file_path: str, bucket_name: str, object_name: str):
    self.s3_client.upload_file(file_path, bucket_name, object_name)
  
  def add_users(self, canvas_course_id: str, course_name: str):
    """
        Get all users in a course by course ID and add them to uiuc.chat course
        - Student profile does not have access to emails.
        - Currently collecting all names in a list.
        """
    try: 
      course = self.canvas_client.get_course(canvas_course_id)
      users = course.get_users()

      user_names = []
      for user in users:
        user_names.append(user.name)

      print("Collected names: ", user_names)

      if len(user_names) > 0:
        return "Success"
      else:
        return "Failed"
    except Exception as e:
      return "Failed to `add users`! Error: " + str(e)

  def download_course_content(self, canvas_course_id: int, dest_folder: str, content_ingest_dict: dict) -> str:
    """
        Downloads all Canvas course materials through the course ID and stores in local directory.
        1. Iterate through content_ingest_dict and download all.
        2. Maintain a list of URLs and convert HTML strings to proper format.
        """
    print("In download_course_content")

    try:
      api_path = "https://canvas.illinois.edu/api/v1/courses/" + str(canvas_course_id)

      # Iterate over the content_ingest_dict
      for key, value in content_ingest_dict.items():
        if value is True:
          if key == 'files':
            self.download_files(dest_folder, api_path)
          elif key == 'pages':
            self.download_pages(dest_folder, api_path)
          elif key == 'modules':
            self.download_modules(dest_folder, api_path)
          elif key == 'syllabus':
            self.download_syllabus(dest_folder, api_path)
          elif key == 'assignments':
            self.download_assignments(dest_folder, api_path)
          elif key == 'discussions':
            self.download_discussions(dest_folder, api_path)

      # at this point, we have all extracted files in the dest_folder.

      return "Success"
    except Exception as e:
      return "Failed! Error: " + str(e)

  def ingest_course_content(self, canvas_course_id: int, course_name: str, content_ingest_dict: dict = None) -> str:
    """
        Ingests all Canvas course materials through the course ID.
        1. Download zip file from Canvas and store in local directory
        2. Upload all files to S3
        3. Call bulk_ingest() to ingest all files into QDRANT
        4. Delete extracted files from local directory
        """

    print("In ingest_course_content")
    try:
      # a dictionary of all contents we want to ingest - files, pages, modules, syllabus, assignments, discussions.
      if content_ingest_dict is None:
        content_ingest_dict = {
            'files': True,
            'pages': True,
            'modules': True,
            'syllabus': True,
            'assignments': True,
            'discussions': True
        }

      # Create a canvas directory with a course folder inside it.
      canvas_dir = "canvas_materials"
      folder_name = "canvas_course_" + str(canvas_course_id) + "_ingest"
      folder_path = canvas_dir + "/" + folder_name

      if os.path.exists(canvas_dir):
        print("Canvas directory already exists")
      else:
        os.mkdir(canvas_dir)
        print("Canvas directory created")

      if os.path.exists(canvas_dir + "/" + folder_name):
        print("Course folder already exists")
      else:
        os.mkdir(canvas_dir + "/" + folder_name)
        print("Course folder created")

      # Download course content
      self.download_course_content(canvas_course_id, folder_path, content_ingest_dict)

      # Upload files to S3

      # get a list of ALL files (recursive) in folder_path
      all_file_paths = [os.path.join(dp, f) for dp, dn, filenames in os.walk(folder_path) for f in filenames]

      all_s3_paths = []
      all_readable_filenames = []
      # Upload each file to S3
      for file_path in all_file_paths:
        file_name = file_path.split('/')[-1]
        extension = file_name[file_name.rfind('.'):]
        name_without_extension = re.sub(r'[^a-zA-Z0-9]', '-', file_name[:file_name.rfind('.')])
        uid = str(uuid.uuid4()) + '-'
        
        unique_filename = uid + name_without_extension + extension
        readable_filename = name_without_extension + extension
        all_s3_paths.append(unique_filename)
        all_readable_filenames.append(readable_filename)
        print("Uploading file: ", readable_filename)
        self.upload_file(file_path, os.getenv('S3_BUCKET_NAME'), unique_filename)

      # Delete files from local directory
      shutil.rmtree(folder_path)

      # Ingest files
      url = 'https://41kgx.apps.beam.cloud'
      headers = {'Authorization': f"Basic {os.getenv('BEAM_API_KEY')}",}

      print("Number of docs to ingest: ", len(all_s3_paths))
      for s3_path, readable_filename in zip(all_s3_paths, all_readable_filenames): 
        data = {
          'course_name': course_name,
          'readable_filename': readable_filename,
          's3_paths': s3_path,

          'base_url': "https://canvas.illinois.edu/courses/" + str(canvas_course_id),
        }
        print("Posting S3 path: ", s3_path, "\nreadable_filename: ", readable_filename)
        response = requests.post(url, headers=headers, data=json.dumps(data))
        print("response=", response.json())

      # legacy method
      # ingest = Ingest()
      # canvas_ingest = ingest.bulk_ingest(s3_paths, course_name=course_name)
      return canvas_ingest

    except Exception as e:
      print(e)
      return "Failed"

  def download_files(self, dest_folder: str, api_path: str) -> str:
    """
        Downloads all files in a Canvas course into given folder.
        """
    try:
      # files_request = requests.get(api_path + "/files", headers=self.headers)
      # files = files_request.json()

      course = self.canvas_client.get_course(api_path.split('/')[-1])
      files = course.get_files()

      for file in files:
        # file_name = file['filename']
        file_name = file.filename
        print("Downloading file: ", file_name)

        # file_download = requests.get(file['url'], headers=self.headers)
        file_download = requests.get(file.url, headers=self.headers)
        with open(os.path.join(dest_folder, file_name), 'wb') as f:
          f.write(file_download.content)

      return "Success"
    except Exception as e:
      return "Failed! Error: " + str(e)

  def download_pages(self, dest_folder: str, api_path: str) -> str:
    """
        Downloads all pages as HTML and stores them in given folder.
        """
    print("In download_pages")
    try:
      pages_request = requests.get(api_path + "/pages", headers=self.headers)
      pages = pages_request.json()

      for page in pages:
        if page['html_url'] != '':
          page_name = page['url'] + ".html"
          page_content_request = requests.get(api_path + "/pages/" + str(page['page_id']), headers=self.headers)
          page_body = page_content_request.json()['body']

          with open(dest_folder + "/" + page_name, 'w') as html_file:
            html_file.write(page_body)

      return "Success"
    except Exception as e:
      return "Failed! Error: " + str(e)

  def download_syllabus(self, dest_folder: str, api_path: str) -> str:
    """
        Downloads syllabus as HTML and stores in given folder.
        """
    print("In download_syllabus")
    try:
      course_settings_request = requests.get(api_path + "?include=syllabus_body", headers=self.headers)
      syllabus_body = course_settings_request.json()['syllabus_body']
      syllabus_name = "syllabus.html"

      with open(dest_folder + "/" + syllabus_name, 'w') as html_file:
        html_file.write(syllabus_body)
      return "Success"
    except Exception as e:
      return "Failed! Error: " + str(e)

  def download_modules(self, dest_folder: str, api_path: str) -> str:
    """
        Downloads all content uploaded in modules.
        Modules may contain: assignments, quizzes, files, pages, discussions, external tools and external urls.
        Rest of the things are covered in other functions.
        """
    print("In download_modules")
    try:
      module_request = requests.get(api_path + "/modules?include=items", headers=self.headers)
      modules = module_request.json()

      for module in modules:
        module_items = module['items']
        for item in module_items:
          if item['type'] == 'ExternalUrl':
            external_url = item['external_url']
            url_title = item['title']

            # Download external url as HTML
            response = requests.get(external_url)
            if response.status_code == 200:
              html_file_name = url_title + ".html"
              with open(dest_folder + "/" + html_file_name, 'w') as html_file:
                html_file.write(response.text)
      return "Success"
    except Exception as e:
      return "Failed! Error: " + str(e)

  def download_assignments(self, dest_folder: str, api_path: str) -> str:
    """
        The description attribute has the assignment content in HTML format. Access that and store it as an HTML file.
        """
    print("In download_assignments")
    try:
      assignment_request = requests.get(api_path + "/assignments", headers=self.headers)
      assignments = assignment_request.json()

      for assignment in assignments:
        if assignment['description'] is not None and assignment['description'] != "":
          assignment_name = "assignment_" + str(assignment['id']) + ".html"
          assignment_description = assignment['description']

          with open(dest_folder + "/" + assignment_name, 'w') as html_file:
            html_file.write(assignment_description)
      return "Success"
    except Exception as e:
      return "Failed! Error: " + str(e)

  def download_discussions(self, dest_folder: str, api_path: str) -> str:
    """
        Download course discussions as HTML and store in given folder.
        """
    print("In download_discussions")
    try:
      discussion_request = requests.get(api_path + "/discussion_topics", headers=self.headers)
      discussions = discussion_request.json()

      for discussion in discussions:
        discussion_content = discussion['message']
        discussion_name = discussion['title'] + ".html"

        with open(dest_folder + "/" + discussion_name, 'w') as html_file:
          html_file.write(discussion_content)
      return "Success"
    except Exception as e:
      return "Failed! Error: " + str(e)