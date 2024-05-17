from abc import ABC, abstractmethod
from typing import List

class BaseVectorDatabase(ABC):

  @abstractmethod
  def vector_search(self, search_query, course_name, doc_groups: List[str], user_query_embedding, top_n):
    pass

  @abstractmethod
  def delete_data(self, collection_name: str, key: str, value: str):
    pass
