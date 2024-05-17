import os
from typing import List

from injector import inject
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Qdrant
from qdrant_client import QdrantClient, models

OPENAI_API_TYPE = "azure"  # "openai" or "azure"


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
        embeddings=OpenAIEmbeddings(openai_api_type=OPENAI_API_TYPE),
    )

  def vector_search(self, search_query, course_name, doc_groups: List[str], user_query_embedding, top_n):
    """
    Search the vector database for a given query.
    """
    myfilter = self._create_search_conditions(course_name, doc_groups)

    # Filter for the must_conditions
    # myfilter = models.Filter(must=must_conditions)
    # print(f"Filter: {myfilter}")

    # Search the vector database
    search_results = self.qdrant_client.search(
        collection_name=os.environ['QDRANT_COLLECTION_NAME'],
        query_filter=myfilter,
        with_vectors=False,
        query_vector=user_query_embedding,
        limit=top_n,  # Return n closest points
        # In a system with high disk latency, the re-scoring step may become a bottleneck: https://qdrant.tech/documentation/guides/quantization/
        search_params=models.SearchParams(quantization=models.QuantizationSearchParams(rescore=False)))
    return search_results

  def _create_search_conditions(self, course_name, doc_groups: List[str]):
    """
    Create search conditions for the vector search.

    The search conditions are as follows:
      * Main query: (course_name AND doc_groups) OR (public_doc_groups)
      * if 'All Documents' enabled, then add filter to exclude disabled_doc_groups
    """
    # Match course name
    must_conditions: list[models.Condition] = [
        models.FieldCondition(key='course_name', match=models.MatchValue(value=course_name))
    ]

    # Return all documents, except those in disabled doc_groups
    if 'All Documents' in doc_groups:
      # TODO: get disabled_doc_groups from Supabase...
      f = models.Filter.must_not(
          models.FieldCondition(key='doc_groups', match=models.MatchValue(value=disabled_doc_groups)))
      must_conditions.append(f)

    # Return ONLY documents in specified doc_groups
    if doc_groups and 'All Documents' not in doc_groups:
      # Condition for matching any of the specified doc_groups
      combined_condition = models.Filter(
          should=[models.FieldCondition(key='doc_groups', match=models.MatchAny(any=doc_groups))])
      must_conditions.append(combined_condition)

    # TODO: get list of public_doc_groups to match from Supabase
    # Additionally, return any matching public doc_groups the project is subscribed to.
    public_doc_groups_condition = None
    if public_doc_groups:
      public_doc_groups_condition = models.FieldCondition(key='doc_groups',
                                                          match=models.MatchAny(value=public_doc_groups))

    # Return all course documents, and public doc groups.
    # Boolean expression: (course_name AND doc_groups) OR (public_doc_groups)
    final_filter = models.Filter(should=[models.Filter(must=[must_conditions]), public_doc_groups_condition])

    print(f"Filter: {final_filter}")
    return final_filter

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
