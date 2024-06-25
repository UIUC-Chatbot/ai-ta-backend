import os
from typing import List

from injector import inject
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Qdrant
from qdrant_client import QdrantClient, models


class VectorDatabase():
  """
  Contains all methods for building and using vector databases.
  """

  @inject
  def __init__(self):
    """
    Initialize AWS S3, Qdrant, and Supabase.
    """
    # vector DB
    self.qdrant_client = QdrantClient(
        url=os.environ['QDRANT_URL'],
        api_key=os.environ['QDRANT_API_KEY'],
        timeout=20,  # default is 5 seconds. Getting timeout errors w/ document groups.
    )

    self.vectorstore = Qdrant(
        client=self.qdrant_client,
        collection_name=os.environ['QDRANT_COLLECTION_NAME'],
        embeddings=OpenAIEmbeddings(openai_api_type=os.environ['OPENAI_API_TYPE']),  # "openai" or "azure"
    )

  def vector_search(self, search_query, course_name, doc_groups: List[str], user_query_embedding, top_n,
                    disabled_doc_groups: List[str]):
    """
    Search the vector database for a given query.
    """
    # Search the vector database
    search_results = self.qdrant_client.search(
        collection_name=os.environ['QDRANT_COLLECTION_NAME'],
        query_filter=self._create_search_filter(course_name, doc_groups, disabled_doc_groups),
        with_vectors=False,
        query_vector=user_query_embedding,
        limit=top_n,  # Return n closest points
        # In a system with high disk latency, the re-scoring step may become a bottleneck: https://qdrant.tech/documentation/guides/quantization/
        search_params=models.SearchParams(quantization=models.QuantizationSearchParams(rescore=False)))
    return search_results

  def _create_search_filter(self, course_name, doc_groups: List[str], disabled_doc_groups: List[str]) -> models.Filter:
    """
    Create search conditions for the vector search.
    """
    must_conditions: list[models.Condition] = [
        models.FieldCondition(key='course_name', match=models.MatchValue(value=course_name)),
    ]

    if doc_groups and 'All Documents' not in doc_groups:
      # Final combined condition
      combined_condition = None
      # Condition for matching any of the specified doc_groups
      match_any_condition = models.FieldCondition(key='doc_groups', match=models.MatchAny(any=doc_groups))
      combined_condition = models.Filter(should=[match_any_condition])

      # Add the combined condition to the must_conditions list
      must_conditions.append(combined_condition)

    must_not_conditions: list[models.Condition] = []

    if disabled_doc_groups:
      # Condition for not matching any of the specified doc_groups
      must_not_conditions = [models.FieldCondition(key='doc_groups', match=models.MatchAny(any=disabled_doc_groups))]

    vector_search_filter = models.Filter(must=must_conditions, must_not=must_not_conditions)
    print(f"Vector search filter: {vector_search_filter}")
    return vector_search_filter

  def delete_data(self, collection_name: str, key: str, value: str):
    """
    Delete data from the vector database.
    """
    return self.qdrant_client.delete(
        collection_name=collection_name,
        points_selector=models.Filter(must=[
            models.FieldCondition(
                key=key,
                match=models.MatchValue(value=value),
            ),
        ]),
    )
