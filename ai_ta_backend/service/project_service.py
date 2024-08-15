import os
import time
from injector import inject

from ai_ta_backend.database.sql import SQLDatabase
from ai_ta_backend.service.posthog_service import PosthogService
from ai_ta_backend.service.sentry_service import SentryService


class ProjectService:
    """
    This class contains all methods related to project management.
    """
    @inject
    def __init__(self, sql_db: SQLDatabase, posthog_service: PosthogService, sentry_service: SentryService):
        self.sqlDb = sql_db
        self.posthog = posthog_service
        self.sentry = sentry_service

    def create_project(self, project_name: str, project_description: str) -> str:
        """
        Create a new project.
        """
        print("Inside create_project")
        print("project_name: ", project_name)
        print("project_description: ", project_description)

        return "success"
        

