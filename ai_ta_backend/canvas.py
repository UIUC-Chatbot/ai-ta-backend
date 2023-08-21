import os
import shutil
from canvasapi import Canvas
import requests
from zipfile import ZipFile
from ai_ta_backend.aws import upload_data_files_to_s3
from ai_ta_backend.vector_database import Ingest
from ai_ta_backend import update_materials


class CanvasAPI():
    def __init__(self):
        self.canvas_client = Canvas("https://canvas.illinois.edu", 
                                    os.getenv('CANVAS_ACCESS_TOKEN'))
        self.headers = {"Authorization": "Bearer " + os.getenv('CANVAS_ACCESS_TOKEN')}
    
    def add_users(self, canvas_course_id: str, course_name: str):
        """
        Get all users in a course by course ID and add them to uiuc.chat course
        - Currently collecting all email IDs in a list.
        """
        course = self.canvas_client.get_course(canvas_course_id)
        users = course.get_users()
        user_emails = []
        for user in users:
            net_id = user.sis_user_id
            email_id = net_id + "@illinois.edu"
            user_emails.append(email_id)
        
        print(user_emails)
        
        if len(user_emails) > 0:
            return "Success"
        else:
            return "Failed"
        
    def download_course_content(self, canvas_course_id: int, dest_folder: str) -> str:
        """
        Downloads all Canvas course materials through the course ID and stores in local directory.
        1. Export content as zip file
        2. Extract files into given directory
        3. Delete zip file
        """
        print("In download_course_content")
        try:
            api_path = "https://canvas.illinois.edu/api/v1/courses/" + str(canvas_course_id)
            # Start content export
            content_export_api_path = api_path + "/content_exports?export_type=zip"
            start_content_export = requests.post(content_export_api_path, headers=self.headers)
            content_export_id = start_content_export.json()['id']
            progress_url = start_content_export.json()['progress_url']

            # Wait for the content export to finish
            export_progress = requests.get(progress_url, headers=self.headers)
            while export_progress.json()['workflow_state'] != 'completed':
                export_progress = requests.get(progress_url, headers=self.headers)
            
            # View content export and get download URL
            show_content_export_api_path = api_path + "/content_exports/" + str(content_export_id)
            print("Show export path: ", show_content_export_api_path)

            show_content_export = requests.get(show_content_export_api_path, headers=self.headers)
            download_url = show_content_export.json()['attachment']['url']
            file_name = show_content_export.json()['attachment']['filename']

            # Create a directory for the content
            directory = os.path.join(os.getcwd(), dest_folder)
            
            if not os.path.exists(directory):
                print("path doesn't exist")
                try:
                    os.mkdir(directory)
                except OSError as e:
                    print(e)

            # Download zip and save to directory
            download = requests.get(download_url, headers=self.headers)
            with open(os.path.join(dest_folder, file_name), 'wb') as f:
                f.write(download.content)
            print("Downloaded!")

            # Extract and read from zip file
            filepath = dest_folder + "/" + file_name
            with ZipFile(filepath, 'r') as zip:
                zip.printdir()
                zip.extractall(dest_folder)
                print('Done!')
            os.remove(filepath)

            return "Success"
        except Exception as e:
            return "Failed! Error: " + str(e)


    def ingest_course_content(self, canvas_course_id: int, course_name: str)-> str:
        """
        Ingests all Canvas course materials through the course ID.
        1. Download zip file from Canvas and store in local directory
        2. Upload all files to S3
        3. Call bulk_ingest() to ingest all files into QDRANT
        4. Delete extracted files from local directory
        """
        print("In ingest_course_content")
        try:
            # Download files into course_content folder
            folder_name = "canvas_course_" + str(canvas_course_id) + "_ingest"
            folder_path = "canvas_materials/" + folder_name

            self.download_course_content(canvas_course_id, folder_path)
            
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
        
    def update_course_content(self, canvas_course_id: int, course_name: str) -> str:
        """
        Updates all Canvas course materials through the course ID.
        1. Download zip file from Canvas
        2. Perform diff between downloaded files and existing S3 files
        3. Replace the changed files in S3 and QDRANT
        """
        print("In update_course_content")

        api_path = "https://canvas.illinois.edu/api/v1/courses/" + str(canvas_course_id)
        headers = {"Authorization": "Bearer " + os.getenv('CANVAS_ACCESS_TOKEN')}

        try:
            # Download course content
            folder_name = "canvas_course_" + str(canvas_course_id) + "_update"
            folder_path = os.path.join(os.getcwd(), "canvas_materials/" + folder_name)
            self.download_course_content(canvas_course_id, folder_path)

            # Call diff function
            response = update_materials.update_files(folder_path, course_name)
            print(response)
            return response
        except Exception as e:
            return "Failed! Error: " + str(e)
        