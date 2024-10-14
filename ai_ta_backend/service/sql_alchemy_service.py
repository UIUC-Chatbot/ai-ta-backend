import os
from injector import inject
from ai_ta_backend.database.sql import SQLAlchemyDatabase

class SQLAlchemyService:
    @inject
    def __init__(self, sqlDb: SQLAlchemyDatabase):
        self.sql_db = sqlDb

    def getAllMaterialsForCourse(self, course_name):
        result = self.sql_db.getAllMaterialsForCourse(course_name)
        return result
    
    def getMaterialsForCourseAndS3Path(self, course_name, s3_path):
        result = self.sql_db.getMaterialsForCourseAndS3Path(course_name, s3_path)
        return result
    
    def deleteMaterialsForCourseAndS3Path(self, course_name, s3_path):
        result = self.sql_db.deleteMaterialsForCourseAndS3Path(course_name, s3_path)
        return result
    
    def getDocumentsBetweenDates(self, course_name, start_date, end_date):
        result = self.sql_db.getDocumentsBetweenDates(course_name, start_date, end_date)
        return result
    
    def getProjectsMapForCourse(self, course_name):
        result = self.sql_db.getProjectsMapForCourse(course_name)
        return result

    def insertProjectInfo(self, project_info):
        result = self.sql_db.insertProjectInfo(project_info)
        return result
    
    def getConvoMapFromProjects(self, course_name):
        result = self.sql_db.getDocMapFromProjects(course_name)
        return result
    
    def updateProjects(self, course_name, data):
        result = self.sql_db.updateProjects(course_name, data)
        return result
    
    def insertProject(self, project_info):
        result = self.sql_db.insertProject(project_info)
        return result
    
    def getCountFromLLMConvoMonitor(self, course_name, last_id):
        result = self.sql_db.getCountFromLLMConvoMonitor(course_name, last_id)
        return result
    
    def getConversation(self, course_name, key, value):
        result = self.sql_db.getConversation(course_name, key, value)
        return result
    
    def getLatestWorkflowId(self):
        result = self.sql_db.getLatestWorkflowId()
        return result
    
    def check_and_lock_flow(self, id):
        result = self.sql_db.check_and_lock_flow(id)
        return result

    def getPreAssignedAPIKeys(self, email):
        result = self.sql_db.getPreAssignedAPIKeys(email)
        return result
    
    def getDisabledDocGroups(self, course_name):
        result = self.sql_db.getDisabledDocGroups(course_name)
        return result
