import os
from injector import inject
from ai_ta_backend.database.sql import SQLAlchemyDatabase

class SQLAlchemyService:
    @inject
    def __init__(self, sqlDb: SQLAlchemyDatabase):
        self.sql_db = sqlDb

    def getAllMaterialsForCourse(self, course_name):
        print("Getting all materials for course: ", course_name)
        result = self.sql_db.getAllMaterialsForCourse(course_name)
        print("Result: ", result)
        return result