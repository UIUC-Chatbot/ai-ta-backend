import os
from typing import List

from injector import inject
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Qdrant
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import FieldCondition, MatchAny, MatchValue


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
        port=os.getenv('QDRANT_PORT') if os.getenv('QDRANT_PORT') else None,
        timeout=20,  # default is 5 seconds. Getting timeout errors w/ document groups.
    )

    self.vectorstore = Qdrant(client=self.qdrant_client,
                              collection_name=os.environ['QDRANT_COLLECTION_NAME'],
                              embeddings=OpenAIEmbeddings(openai_api_key=os.environ['VLADS_OPENAI_KEY']))

  def vector_search(self, search_query, course_name, doc_groups: List[str], user_query_embedding, top_n,
                    disabled_doc_groups: List[str], public_doc_groups: List[dict]):
    """
    Search the vector database for a given query.
    """
    # Search the vector database
    search_results = self.qdrant_client.search(
        collection_name=os.environ['QDRANT_COLLECTION_NAME'],
        query_filter=self._create_search_filter(course_name, doc_groups, disabled_doc_groups, public_doc_groups),
        with_vectors=False,
        query_vector=user_query_embedding,
        limit=top_n,  # Return n closest points
        # In a system with high disk latency, the re-scoring step may become a bottleneck: https://qdrant.tech/documentation/guides/quantization/
        search_params=models.SearchParams(quantization=models.QuantizationSearchParams(rescore=False)))
    # print(f"Search results: {search_results}")
    return search_results

  def _create_search_filter(self, course_name: str, doc_groups: List[str], admin_disabled_doc_groups: List[str],
                            public_doc_groups: List[dict]) -> models.Filter:
    """
    Create search conditions for the vector search.
    """

    must_conditions = []
    should_conditions = []

    # Exclude admin-disabled doc_groups
    must_not_conditions = []
    if admin_disabled_doc_groups:
      must_not_conditions.append(FieldCondition(key='doc_groups', match=MatchAny(any=admin_disabled_doc_groups)))

    # Handle public_doc_groups
    if public_doc_groups:
      for public_doc_group in public_doc_groups:
        if public_doc_group['enabled']:
          # Create a combined condition for each public_doc_group
          combined_condition = models.Filter(must=[
              FieldCondition(key='course_name', match=MatchValue(value=public_doc_group['course_name'])),
              FieldCondition(key='doc_groups', match=MatchAny(any=[public_doc_group['name']]))
          ])
          should_conditions.append(combined_condition)

    # Handle user's own course documents
    own_course_condition = models.Filter(must=[FieldCondition(key='course_name', match=MatchValue(value=course_name))])

    # If specific doc_groups are specified
    if doc_groups and 'All Documents' not in doc_groups:
      own_course_condition.must.append(FieldCondition(key='doc_groups', match=MatchAny(any=doc_groups)))

    # Add the own_course_condition to should_conditions
    should_conditions.append(own_course_condition)

    # Construct the final filter
    vector_search_filter = models.Filter(should=should_conditions, must_not=must_not_conditions)

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
