from typing import List
from injector import inject
from flask_sqlalchemy import SQLAlchemy
import ai_ta_backend.model.models as models
import logging

from ai_ta_backend.model.response import DatabaseResponse

class POISQLDatabase:

    @inject
    def __init__(self, db: SQLAlchemy):  
        logging.info("Initializing SQLAlchemyDatabase")
        self.db = db