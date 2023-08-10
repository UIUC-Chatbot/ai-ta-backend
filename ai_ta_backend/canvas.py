# import required libraries
import os
from dotenv import load_dotenv
from canvasapi import Canvas


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
        