import os
import time
import json
import requests
from injector import inject

from ollama import Client


from ai_ta_backend.database.sql import SQLDatabase
from ai_ta_backend.service.posthog_service import PosthogService
from ai_ta_backend.service.sentry_service import SentryService
from ai_ta_backend.utils.schema_generation import generate_schema_from_project_description


class ProjectService:
    """
    This class contains all methods related to project management.
    """
    @inject
    def __init__(self, sql_db: SQLDatabase, posthog_service: PosthogService, sentry_service: SentryService):
        self.sqlDb = sql_db
        self.posthog = posthog_service
        self.sentry = sentry_service
        self.ollama = Client(host="https://secret-ollama.ncsa.ai")
        self.llm = 'llama3.1:70b'

    def create_project(self, project_name: str, project_description: str) -> str:
        """
        This function takes in a project name and description and creates a project in the database.
        1. Generate metadata schema using project_name and project_description
        2. Insert project into Supabase
        3. Insert project into Redis
        """
        print("Inside create_project")
        print("project_name: ", project_name)
        print("project_description: ", project_description)
        try:
            # Generate metadata schema using project_name and project_description
            json_schema = generate_schema_from_project_description(project_name, project_description)
            
            # Insert project into Supabase
            sql_row = {
                "course_name": project_name,
                "description": project_description,
                "metadata_schema": json_schema,
            }
            response = self.sqlDb.insertProject(sql_row)
            print("Response from insertProject: ", response)

            # Insert project into Redis
            headers = {
                "Authorization": f"Bearer {os.environ['KV_REST_API_TOKEN']}",  # Ensure you use the appropriate write-access API key
                "Content-Type": "application/json"
            }
            # Define the key-value pair you want to insert
            key = project_name  # Replace with your key
            value = {
                "project_description": project_description,
            }  

            # Construct the URL for the HSET request
            hset_url = str(os.environ['KV_REST_API_URL']) + f"/hset/course_metadatas/{key}"

            # Make the POST request to insert the key-value pair
            response = requests.post(hset_url, headers=headers, data=json.dumps(value))

            # Check the response status
            if response.status_code == 200:
                print("Key-value pair inserted successfully.")
            else:
                print(f"Failed to insert key-value pair. Status code: {response.status_code}, Response: {response.text}")

            return "success"
        except Exception as e:
            print("Error in create_project: ", e)
            return "error"
        

