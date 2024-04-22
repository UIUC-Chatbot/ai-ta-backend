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
    # print(f"Searching for: {search_query} with doc_groups: {doc_groups}")
    must_conditions: list[models.Condition] = [
        models.FieldCondition(key='course_name', match=models.MatchValue(value=course_name))
    ]
    if doc_groups and doc_groups != []:
      # Condition for matching any of the specified doc_groups
      match_any_condition = models.FieldCondition(key='doc_groups', match=models.MatchAny(any=doc_groups))
      # Condition for matching documents where doc_groups is not set
      is_empty_condition = models.IsEmptyCondition(is_empty=models.PayloadField(key="doc_groups"))
      # Combine the above conditions using a should clause to create a logical OR condition
      combined_condition = models.Filter(should=[match_any_condition, is_empty_condition])
      must_conditions.append(combined_condition)
    myfilter = models.Filter(must=must_conditions)
    print(f"Filter: {myfilter}")
    search_results = self.qdrant_client.search(
        collection_name=os.environ['QDRANT_COLLECTION_NAME'],
        query_filter=myfilter,
        with_vectors=False,
        query_vector=user_query_embedding,
        limit=top_n,  # Return n closest points

        # In a system with high disk latency, the re-scoring step may become a bottleneck: https://qdrant.tech/documentation/guides/quantization/
        search_params=models.SearchParams(quantization=models.QuantizationSearchParams(rescore=False)))
    return search_results

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
