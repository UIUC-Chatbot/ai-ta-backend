"""
To deploy: beam deploy canvas_ingest.py
Use CAII gmail to auth.
"""

import json
import os
import re
import shutil
import uuid
from typing import Any, Dict, List

import beam
import boto3
import requests
import sentry_sdk
from beam import App, QueueDepthAutoscaler, Runtime  # RequestLatencyAutoscaler,
from canvasapi import Canvas
from posthog import Posthog
from bs4 import BeautifulSoup
import yt_dlp

requirements = [
    "boto3==1.28.79",
    "posthog==3.1.0",
    "canvasapi==3.2.0",
    "sentry-sdk==1.39.1",
    "bs4==0.0.2",
    "yt-dlp==2024.7.16",
]

app = App(
    "canvas_ingest",
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

  # Init sentry, but no need to pass it around.
  sentry_sdk.init(
      dsn="https://examplePublicKey@o0.ingest.sentry.io/0",
      enable_tracing=True,
  )

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
  """
  Main function.
  Params:
    course_name: str
    canvas_url: str
  """
  s3_client, canvas_client, posthog = inputs["context"]

  course_name: List[str] | str = inputs.get('course_name', '')
  canvas_url: List[str] | str | None = inputs.get('canvas_url', None)
  # Options:
  files: bool = inputs.get('files', True)
  pages: bool = inputs.get('pages', True)
  modules: bool = inputs.get('modules', True)
  syllabus: bool = inputs.get('syllabus', True)
  assignments: bool = inputs.get('assignments', True)
  discussions: bool = inputs.get('discussions', True)
  options = {
      'files': str(files).lower() == 'true',
      'pages': str(pages).lower() == 'true',
      'modules': str(modules).lower() == 'true',
      'syllabus': str(syllabus).lower() == 'true',
      'assignments': str(assignments).lower() == 'true',
      'discussions': str(discussions).lower() == 'true',
  }
  print(f"{course_name}=")
  print(f"{canvas_url}=")
  print("Download options: ", options)

  try:
    # canvas.illinois.edu/courses/COURSE_CODE
    match = re.search(r'canvas\.illinois\.edu/courses/([^/]+)', canvas_url)
    canvas_course_id = match.group(1) if match else None

    ingester = CanvasIngest(s3_client, canvas_client, posthog)
    ingester.ingest_course_content(canvas_course_id=canvas_course_id,
                                   course_name=course_name,
                                   content_ingest_dict=options)

    # Can get names, but not emails. e.g. Collected names:  ['UIUC Course AI', 'Shannon Bradley', 'Asmita Vijay Dabholkar', 'Kastan Day', 'Volodymyr Kindratenko', 'Max Lindsey', 'Rohan Marwaha', 'Joshua Min', 'Neha Sheth', 'George Tamas']
    # ingester.add_users(canvas_course_id, course_name)
  except Exception as e:
    print("Top level error:", e)
    sentry_sdk.capture_exception(e)
    return "Failed"


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
      sentry_sdk.capture_exception(e)
      return "Failed to `add users`! Error: " + str(e)

  def download_course_content(self, canvas_course_id: int, dest_folder: str, content_ingest_dict: dict) -> str:
    """
    Downloads all Canvas course materials through the course ID and stores in local directory.
    1. Iterate through content_ingest_dict and download all.
    2. Maintain a list of URLs and convert HTML strings to proper format.
    """
    print("In download_course_content")

    print(f"content_ingest_dict (in final download section) = {content_ingest_dict}")

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

      # at this point, we have all canvas files in the dest_folder.
      # parse all HTML files in dest_folder and extract URLs
      extracted_urls_from_html = self.extract_urls_from_html(dest_folder)
      #print("extract_urls_from_html=", extract_urls_from_html)

      # links - canvas files, external urls, embedded videos
      file_links = extracted_urls_from_html.get('file_links', [])
      
      video_links = extracted_urls_from_html.get('video_links', [])
      #external_links = extract_urls_from_html.get('external_links', [])

      # download files from URLs
      file_download_status = self.download_files_from_urls(file_links, canvas_course_id, dest_folder)
      video_download_status = self.download_videos_from_urls(video_links, canvas_course_id, dest_folder)
      print("file_download_status=", file_download_status)
      print("video_download_status=", video_download_status)

      return "Success"
    except Exception as e:
      sentry_sdk.capture_exception(e)
      return "Failed! Error: " + str(e)

  def ingest_course_content(self,
                            canvas_course_id: int,
                            course_name: str,
                            content_ingest_dict: Dict[str, bool] = None) -> str:
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

      print("{content_ingest_dict}=")
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
        s3_path = "courses/" + course_name + "/" + unique_filename
        readable_filename = name_without_extension + extension
        all_s3_paths.append(s3_path)
        all_readable_filenames.append(readable_filename)
        print("Uploading file: ", readable_filename)
        print("Filepath: ", file_path)
        self.upload_file(file_path, os.getenv('S3_BUCKET_NAME'), s3_path)

      # Delete files from local directory
      shutil.rmtree(folder_path)

      # Ingest files
      url = 'https://41kgx.apps.beam.cloud'
      headers = {
          'Authorization': f"Basic {os.getenv('BEAM_API_KEY')}",
      }

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
      sentry_sdk.capture_exception(e)
      return "Failed"

  def download_files(self, dest_folder: str, api_path: str) -> str:
    """
    Downloads all files in a Canvas course into given folder.
    """
    print("In download_files")
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
      sentry_sdk.capture_exception(e)
      return "Failed! Error: " + str(e)

  def download_pages(self, dest_folder: str, api_path: str) -> str:
    """
    Downloads all pages as HTML and stores them in given folder.
    """
    print("In download_pages")
    try:
      pages_request = requests.get(api_path + "/pages", headers=self.headers)
      pages = pages_request.json()
      #print("Pages: ", pages)
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
      sentry_sdk.capture_exception(e)
      return "Failed! Error: " + str(e)

  def download_modules(self, dest_folder: str, api_path: str) -> str:
    """
    Downloads all content uploaded in modules.
    Modules may contain: assignments, quizzes, files, pages, discussions, external tools and external urls.
    Rest of the things are covered in other functions.
    """
    print("In download_modules")
    # need to parse pages through modules
    try:
      module_request = requests.get(api_path + "/modules?include=items", headers=self.headers)
      
      modules = module_request.json()

      for module in modules:
        module_items = module['items']
        for item in module_items:
          if item['type'] == 'ExternalUrl': # EXTERNAL LINK
            external_url = item['external_url']
            url_title = item['title']

            # Download external url as HTML
            response = requests.get(external_url)
            if response.status_code == 200:
              html_file_name = "external_link_" + url_title.replace(" ", "_") + ".html"
              with open(dest_folder + "/" + html_file_name, 'w') as html_file:
                html_file.write(response.text)
          
          elif item['type'] == 'Discussion':  # DISCUSSION
            discussion_url = item['url']
            discussion_req = requests.get(discussion_url, headers=self.headers)

            if discussion_req.status_code == 200:
              discussion_data = discussion_req.json()
              discussion_message = discussion_data['message']
              discussion_filename = "Discussion_" + discussion_data['title'].replace(" ", "_") + ".html"

              # write the message to a file
              with open(dest_folder + "/" + discussion_filename, 'w') as html_file:
                html_file.write(discussion_message)

          elif item['type'] == 'Assignment':  # ASSIGNMENT
            print("Assigments are handled via download_assignments()")
            continue

          elif item['type'] == 'Quiz': 
            #print("Quizzes are not handled at the moment.")
            continue

          else: # OTHER ITEMS - PAGES
            if 'url' not in item:
              #print("No URL in item: ", item['type'])
              continue

            item_url = item['url']
            item_request = requests.get(item_url, headers=self.headers)
            
            if item_request.status_code == 200:
              item_data = item_request.json()
              if 'body' not in item_data:
                #print("No body in item: ", item_data)
                continue

              item_body = item_data['body']
              html_file_name = item['type'] + "_" + item_data['url'] + ".html"

              # write page body to a file
              with open(dest_folder + "/" + html_file_name, 'w') as html_file:
                html_file.write(item_body)
            else:
              print("Item request failed with status code: ", item_request.status_code)
          
      return "Success"
    except Exception as e:
      sentry_sdk.capture_exception(e)
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
      sentry_sdk.capture_exception(e)
      return "Failed! Error: " + str(e)

  def download_discussions(self, dest_folder: str, api_path: str) -> str:
    """
    Download course discussions as HTML and store in given folder.
    """
    print("In download_discussions")
    try:
      discussion_request = requests.get(api_path + "/discussion_topics", headers=self.headers)
      discussions = discussion_request.json()
      #print("Discussions: ", discussions)
      for discussion in discussions:
        discussion_content = discussion['message']
        discussion_name = discussion['title'] + ".html"

        with open(dest_folder + "/" + discussion_name, 'w') as html_file:
          html_file.write(discussion_content)
      return "Success"
    except Exception as e:
      sentry_sdk.capture_exception(e)
      return "Failed! Error: " + str(e)
    
  def extract_urls_from_html(self, dir_path: str) -> Dict[str, List[str]]:
    """
    Extracts URLs from all HTML files in a directory.
    """
    print("In extract_urls_from_html")
    try:
      file_links = []
      video_links = []
      external_links = []
      for file_name in os.listdir(dir_path):
        if file_name.endswith(".html"):
          file_path = os.path.join(dir_path, file_name)
          try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
              content = file.read()
          except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as file:
              content = file.read()
          
          soup = BeautifulSoup(content, 'html.parser')

          # Extracting links from href attributes
          href_links = soup.find_all('a', href=True)
          for link in href_links:
            href = link['href']
            if re.match(r'https://canvas\.illinois\.edu/courses/\d+/files/.*', href):
              file_links.append(href)
            else:
              external_links.append(href)
          
          # Extracting video links from src attributes
          src_links = soup.find_all('iframe', src=True)
          for link in src_links:
            src = link['src']
            if re.match(r'https://ensemble\.illinois\.edu/hapi/v1/contents/.*', src):
              video_links.append(src)

      return {
          'file_links': file_links,
          'video_links': video_links,}  

    except Exception as e:
      sentry_sdk.capture_exception(e)
      return {}
    
  def download_files_from_urls(self, urls: List[str], course_id: int, dir_path: str):
    """
    This function downloads files from a given Canvas course using the URLs provided.
    input: urls - list of URLs scraped from Canvas HTML pages.
    """
    print("In download_files_from_urls")
    #print("Number of URLs: ", len(urls))
    try:
      for url in urls:
        #print("Downloading file from URL: ", url)
        with requests.get(url, stream=True) as r:
          content_type = r.headers.get('Content-Type')
          #print("Content type: ", content_type)
          content_disposition = r.headers.get('Content-Disposition')
          #print("Content disposition: ", content_disposition)
          if content_disposition is None:
            #print("No content disposition")
            continue

          if 'filename=' in content_disposition:
            filename = content_disposition.split('filename=')[1].strip('"')
            #print("local filename: ", filename)
          else:
            #print("No filename in content disposition")
            continue
          
          # write to PDF
          file_path = os.path.join(dir_path, filename)
          with open(file_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
              f.write(chunk)
          print("Downloaded file: ", filename)

      return "Success"
    except Exception as e:
      sentry_sdk.capture_exception(e)
      print("Error downloading files from URLs: ", e)
      return "Failed! Error: " + str(e)
    
  def download_videos_from_urls(self, urls: List[str], course_id: int, dir_path: str):
    """
    This function downloads videos from a given Canvas course using the URLs provided.
    """
    print("In download_videos_from_urls")
    #print("Video URLs: ", len(urls))
    try:
      count = 0
      for url in urls:
        count += 1
        with requests.get(url, stream=True) as r:
          filename = f"{course_id}_video_{count}.mp4"
          
          # download video
          file_path = os.path.join(dir_path, filename)
          ydl_opts = {
                'outtmpl': f'{dir_path}/{course_id}_video_{count}.%(ext)s',  # Dynamic extension
                'format': 'best',  # Best quality format
          }
          with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            ext = info_dict.get('ext', 'mp4')  # Get extension from info, default to mp4
            filename = f"{course_id}_video_{count}.{ext}"
            

          print(f"Video downloaded successfully: {filename}")

      return "Success"
    except Exception as e:
      sentry_sdk.capture_exception(e)
      print("Error downloading videos from URLs: ", e)
      return "Failed! Error: " + str(e)
