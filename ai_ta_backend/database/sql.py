from typing import List
from injector import inject
from flask_sqlalchemy import SQLAlchemy
import ai_ta_backend.model.models as models
import logging

from ai_ta_backend.model.response import DatabaseResponse

class SQLAlchemyDatabase:

    @inject
    def __init__(self, db: SQLAlchemy):  
        logging.info("Initializing SQLAlchemyDatabase")
        self.db = db
        # Ensure an app context is pushed (Flask-Injector will handle this)
        # with current_app.app_context():
        #     db.init_app(current_app)
        #     db.create_all()  # Create tables

    def getAllMaterialsForCourse(self, course_name: str):
        try:
            query = self.db.select(models.Document).where(models.Document.course_name == course_name)
            result = self.db.session.execute(query).scalars().all()
            documents: List[models.Document] = [doc for doc in result]
            return DatabaseResponse[models.Document](data=documents, count=len(result))
        finally:
            self.db.session.close()

    def getMaterialsForCourseAndS3Path(self, course_name: str, s3_path: str):
        try:
            query = self.db.select(models.Document).where(models.Document.course_name == course_name, models.Document.s3_path == s3_path)
            result = self.db.session.execute(query).scalars().all()
            documents: List[models.Document] = [doc for doc in result]
            return DatabaseResponse[models.Document](data=documents, count=len(result))
        finally:
            self.db.session.close()

    def getMaterialsForCourseAndKeyAndValue(self, course_name: str, key: str, value: str):
        try:
            query = self.db.select(models.Document).where(models.Document.course_name == course_name, getattr(models.Document, key) == value)
            result = self.db.session.execute(query).scalars().all()
            documents: List[models.Document] = [doc for doc in result]
            return DatabaseResponse[models.Document](data=documents, count=len(result))
        finally:
            self.db.session.close()

    def deleteMaterialsForCourseAndKeyAndValue(self, course_name: str, key: str, value: str):
        try:
            query = self.db.delete(models.Document).where(models.Document.course_name == course_name, getattr(models.Document, key) == value)
            self.db.session.execute(query)
            self.db.session.commit()
        finally:
            self.db.session.close()

    def deleteMaterialsForCourseAndS3Path(self, course_name: str, s3_path: str):
        try:
            query = self.db.delete(models.Document).where(models.Document.course_name == course_name, models.Document.s3_path == s3_path)
            self.db.session.execute(query)
            self.db.session.commit()
        finally:
            self.db.session.close()

    def getProjectsMapForCourse(self, course_name: str):
        try:
            query = self.db.select(models.Project.doc_map_id).where(models.Project.course_name == course_name)
            result = self.db.session.execute(query).scalars().all()
            projects: List[models.Project] = [doc for doc in result]
            return DatabaseResponse[models.Project](data=projects, count=len(result))
        finally:
            self.db.session.close()

    def getDocumentsBetweenDates(self, course_name: str, from_date: str, to_date: str):
        try:
            query = self.db.select(models.Document).where(models.Document.course_name == course_name)
            if from_date:
                query = query.filter(models.Document.created_at >= from_date)
            if to_date:
                query = query.filter(models.Document.created_at <= to_date)
            result = self.db.session.execute(query).scalars().all()
            documents: List[models.Document] = [doc for doc in result]
            return DatabaseResponse[models.Document](data=documents, count=len(result))
        finally:
            self.db.session.close()
            
    def getConversationsBetweenDates(self, course_name: str, from_date: str, to_date: str):
        try:
            query = self.db.select(models.LlmConvoMonitor).where(models.LlmConvoMonitor.course_name == course_name)
            if from_date:
                query = query.filter(models.LlmConvoMonitor.created_at >= from_date)
            if to_date:
                query = query.filter(models.LlmConvoMonitor.created_at <= to_date)
            result = self.db.session.execute(query).scalars().all()
            documents: List[models.LlmConvoMonitor] = [doc for doc in result]
            return DatabaseResponse[models.LlmConvoMonitor](data=documents, count=len(result))
        finally:
            self.db.session.close()

    def getAllDocumentsForDownload(self, course_name: str, first_id: int):
        try:
            query = self.db.select(models.Document).where(models.Document.course_name == course_name, models.Document.id >= first_id)
            result = self.db.session.execute(query).scalars().all()
            documents: List[models.Document] = [doc for doc in result]
            return DatabaseResponse[models.Document](data=documents, count=len(result))
        finally:
            self.db.session.close()
            
    def getAllConversationsForDownload(self, course_name: str, first_id: int):
        try:
            query = self.db.select(models.LlmConvoMonitor).where(models.LlmConvoMonitor.course_name == course_name, models.LlmConvoMonitor.id >= first_id)
            result = self.db.session.execute(query).scalars().all()
            conversations: List[models.LlmConvoMonitor] = [doc for doc in result]
            return DatabaseResponse[models.LlmConvoMonitor](data=conversations, count=len(result))
        finally:
            self.db.session.close()

    def getAllConversationsBetweenIds(self, course_name: str, first_id: int, last_id: int, limit: int = 50):
        try:
            query = self.db.select(models.LlmConvoMonitor).where(models.LlmConvoMonitor.course_name == course_name, models.LlmConvoMonitor.id > first_id)
            if last_id != 0:
                query = query.filter(models.LlmConvoMonitor.id <= last_id)
            query = query.limit(limit)
            result = self.db.session.execute(query).scalars().all()
            conversations: List[models.LlmConvoMonitor] = [doc for doc in result]
            return DatabaseResponse[models.LlmConvoMonitor](data=conversations, count=len(result))
        finally:
            self.db.session.close()

    def getDocsForIdsGte(self, course_name: str, first_id: int, fields: str = "*", limit: int = 100):
        try:
            fields_to_select = [getattr(models.Document, field) for field in fields.split(", ")]
            query = self.db.select(*fields_to_select).where(models.Document.course_name == course_name, models.Document.id >= first_id).limit(limit)
            result = self.db.session.execute(query).scalars().all()
            documents: List[models.Document] = [doc for doc in result]
            return DatabaseResponse[models.Document](data=documents, count=len(result))
        finally:
            self.db.session.close()

    def insertProjectInfo(self, project_info):
        try:
            self.db.session.execute(self.db.insert(models.Project).values(**project_info))
            self.db.session.commit()
        finally:
            self.db.session.close()

    def getAllFromLLMConvoMonitor(self, course_name: str):
        try:
            query = self.db.select(models.LlmConvoMonitor).where(models.LlmConvoMonitor.course_name == course_name)
            result = self.db.session.execute(query).scalars().all()
            conversations: List[models.LlmConvoMonitor] = [doc for doc in result]
            return DatabaseResponse[models.LlmConvoMonitor](data=conversations, count=len(result))
        finally:
            self.db.session.close()

    def getCountFromLLMConvoMonitor(self, course_name: str, last_id: int):
        try:
            query = self.db.select(models.LlmConvoMonitor.id).where(models.LlmConvoMonitor.course_name == course_name)
            if last_id != 0:
                query = query.filter(models.LlmConvoMonitor.id > last_id)
            count_query = self.db.select(self.db.func.count()).select_from(query.subquery())
            count = self.db.session.execute(count_query).scalar()
            return DatabaseResponse[models.LlmConvoMonitor](data=[], count=1)
        finally:
            self.db.session.close()

    def getDocMapFromProjects(self, course_name: str):
        try:
            query = self.db.select(models.Project.doc_map_id).where(models.Project.course_name == course_name)
            result = self.db.session.execute(query).scalars().all()
            documents: List[models.Project] = [doc for doc in result]
            return DatabaseResponse[models.Project](data=documents, count=len(result))
        finally:
            self.db.session.close()

    def getConvoMapFromProjects(self, course_name: str):
        try:
            query = self.db.select(models.Project).where(models.Project.course_name == course_name)
            result = self.db.session.execute(query).scalars().all()
            conversations: List[models.Project] = [doc for doc in result]
            return DatabaseResponse[models.Project](data=conversations, count=len(result))
        finally:
            self.db.session.close()

    def updateProjects(self, course_name: str, data: dict):
        try:
            query = self.db.update(models.Project).where(models.Project.course_name == course_name).values(**data)
            self.db.session.execute(query)
            self.db.session.commit()
        finally:
            self.db.session.close()

    def getLatestWorkflowId(self):
        try:
            query = self.db.select(models.N8nWorkflows.latest_workflow_id)
            result = self.db.session.execute(query).fetchone()
            return result
        finally:
            self.db.session.close()

    def lockWorkflow(self, id: str):
        try:
            new_workflow = models.N8nWorkflows(is_locked=True)
            self.db.session.add(new_workflow)
            self.db.session.commit()
        finally:
            self.db.session.close()

    def deleteLatestWorkflowId(self, id: str):
        try:
            query = self.db.delete(models.N8nWorkflows).where(models.N8nWorkflows.latest_workflow_id == id)
            self.db.session.execute(query)
            self.db.session.commit()
        finally:
            self.db.session.close()

    def unlockWorkflow(self, id: str):
        try:
            query = self.db.update(models.N8nWorkflows).where(models.N8nWorkflows.latest_workflow_id == id).values(is_locked=False)
            self.db.session.execute(query)
            self.db.session.commit()
        finally:
            self.db.session.close()

    def getConversation(self, course_name: str, key: str, value: str):
        try:
            query = self.db.select(models.LlmConvoMonitor).where(getattr(models.LlmConvoMonitor, key) == value)
            result = self.db.session.execute(query).scalars().all()
            conversations: List[models.LlmConvoMonitor] = [doc for doc in result]
            return DatabaseResponse[models.LlmConvoMonitor](data=conversations, count=len(result))
        finally:
            self.db.session.close()