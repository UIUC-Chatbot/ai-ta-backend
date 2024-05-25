from typing import List, TypeVar, Generic
from flask_sqlalchemy.model import Model

T = TypeVar('T', bound=Model)

class DatabaseResponse(Generic[T]):
    def __init__(self, data: List[T], count: int):
        self.data = data
        self.count = count