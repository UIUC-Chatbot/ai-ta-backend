import os
import shutil
from canvasapi import Canvas
import requests
from zipfile import ZipFile
from ai_ta_backend.aws import upload_data_files_to_s3
from ai_ta_backend.vector_database import Ingest
from ai_ta_backend import update_materials
from pathlib import Path


class CanvasAPI():
    def __init__(self):
        self.canvas_client = Canvas("https://canvas.illinois.edu", 
                                    os.getenv('CANVAS_ACCESS_TOKEN'))
        self.headers = {"Authorization": "Bearer " + os.getenv('CANVAS_ACCESS_TOKEN')}
    
    def add_users(self, canvas_course_id: str, course_name: str):
        """
        Get all users in a course by course ID and add them to uiuc.chat course
        - Student profile does not have access to emails.
        - Currently collecting all names in a list.
        """
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
                if value == True:
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
            s3_paths = upload_data_files_to_s3(course_name, folder_path)
            
            # Delete files from local directory
            shutil.rmtree(folder_path)

            # Ingest files into QDRANT
            ingest = Ingest()
            canvas_ingest = ingest.bulk_ingest(s3_paths, course_name=course_name)
            return canvas_ingest
        
        except Exception as e:
            print(e)
            return "Failed"
        
    def download_files(self, dest_folder: str, api_path: str) -> str:
        """
        Downloads all files in a Canvas course into given folder.
        """
        try:
            files_request = requests.get(api_path + "/files", headers=self.headers)
            files = files_request.json()

            for file in files:
                file_name = file['filename']
                print("Downloading file: ", file_name)

                file_download = requests.get(file['url'], headers=self.headers)
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
        
    def download_modules(self, dest_folder: str, api_path: str) -> list:
        """
        Returns a list of all external URLs uploaded in modules.
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
                if assignment['description'] is not None:
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

        except Exception as e:
            return "Failed! Error: " + str(e)
        