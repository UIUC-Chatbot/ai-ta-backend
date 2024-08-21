import os
import time
import json
from injector import inject

from ollama import Client
from langchain_core.prompts import PromptTemplate


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



        return "success"
        

