from typing import Generic, List, TypeVar

from flask_sqlalchemy.model import Model

T = TypeVar('T', bound=Model)


class DatabaseResponse(Generic[T]):
    def __init__(self, data: List[T], count: int):
        self._data = data
        self._count = count

    @property
    def data(self) -> List[T]:
        return self._data

    @property
    def count(self) -> int:
        return self._count

    def to_dict(self):
        return {
            "data": self._data,
            "count": self._count
        }