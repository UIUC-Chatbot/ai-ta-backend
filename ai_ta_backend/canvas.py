import os
from canvasapi import Canvas
import requests
from zipfile import ZipFile
from ai_ta_backend.aws import upload_data_files_to_s3
from ai_ta_backend.vector_database import Ingest


class CanvasAPI():
    def __init__(self):
        self.canvas_client = Canvas("https://canvas.illinois.edu", 
                                    os.getenv('CANVAS_ACCESS_TOKEN'))
    
    def add_users(self, canvas_course_id: str, course_name: str):
        """
        Get all users in a course
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
        
    def ingest_course_content(self, canvas_course_id: str, course_name: str):
        """
        Ingests all Canvas course materials through the course ID.
        """
        print("In ingest_course_content")

        api_path = "https://canvas.illinois.edu/api/v1/courses/" + str(canvas_course_id)
        headers = {"Authorization": "Bearer " + os.getenv('CANVAS_ACCESS_TOKEN')}

        try:
            # Start the content export
            content_export_api_path = api_path + "/content_exports?export_type=zip"
            start_content_export = requests.post(content_export_api_path, headers=headers)
            content_export_id = start_content_export.json()['id']
            progress_url = start_content_export.json()['progress_url']

            # Wait for the content export to finish
            export_progress = requests.get(progress_url, headers=headers)
            while export_progress.json()['workflow_state'] != 'completed':
                export_progress = requests.get(progress_url, headers=headers)
            
            # View content export and get download URL
            show_content_export_api_path = api_path + "/content_exports/" + str(content_export_id)
            print("Show export path: ", show_content_export_api_path)

            show_content_export = requests.get(show_content_export_api_path, headers=headers)
            download_url = show_content_export.json()['attachment']['url']
            file_name = show_content_export.json()['attachment']['filename']

            # Create a directory for the content
            directory = os.path.join(os.getcwd(), "course_content")
            if not os.path.exists(directory):
                os.mkdir(directory)

            # Download zip and save to directory
            download = requests.get(download_url, headers=headers)
            with open(os.path.join(directory, file_name), 'wb') as f:
                f.write(download.content)
            print("Downloaded!")

            # Extract and read from zip file
            filepath = "course_content/" + file_name
            with ZipFile(filepath, 'r') as zip:
                zip.printdir()
                zip.extractall("course_content")
                print('Done!')
            os.remove(filepath)

            # Upload files to S3 and call bulk_ingest
            s3_paths = upload_data_files_to_s3(course_name, "course_content")
            ingest = Ingest()
            canvas_ingest = ingest.bulk_ingest(s3_paths, course_name=course_name)
            
            return canvas_ingest
        
        except Exception as e:
            print(e)
            return "Failed"


        