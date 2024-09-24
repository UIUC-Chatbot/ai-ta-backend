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

  def _create_search_filter(self, course_name, doc_groups: List[str], admin_disabled_doc_groups: List[str],
                            public_doc_groups: List[dict]) -> models.Filter:
    """
    Create search conditions for the vector search.
    disabled doc groups are the doc groups disabled by the admin, not the user.
    """

    must_conditions = []
    should_conditions = []
    # TODO: get list of public_doc_groups from
    # public_doc_groups = ['taiga']
    # public_doc_groups = ['Wiley']
    # Extract public_doc_source_project_names and doc_group_names from public_doc_groups and put it in a dict
    # public_doc_groups_dict = [{'source_project_name': doc_group['doc_groups']['source_project_name'], 'doc_group_name': doc_group['doc_groups']['name']} for doc_group in public_doc_groups]
    # Example public_doc_groups_dict:
    # [{'source_project_name': 'ncsa-hydro', 'doc_group_name': 'Wiley'}, {'source_project_name': 'cropwizard-1.5', 'doc_group_name': 'Wiley'}]
    # public_doc_source_project_name = 'ncsa-hydro'
    # public_doc_source_project_name = 'cropwizard-1.5'
    # If public doc groups exist, then we match the source project name and doc group name and the destination course name.
    if public_doc_groups:
      for public_doc_group in public_doc_groups:
        if public_doc_group['enabled']:
          # Match documents that belong to the current course
          should_conditions.append(
              FieldCondition(key='course_name', match=MatchValue(value=public_doc_group['course_name'])))  # destination
          # Match documents that belong to the specific document group of the source project
          should_conditions.append(FieldCondition(key='doc_groups', match=MatchAny(any=[public_doc_group['name']])))
          # Match documents that belong to destination project
          should_conditions.append(FieldCondition(key='course_name', match=MatchValue(value=course_name)))

    else:
      # MUST match ONLY the destination.
      must_conditions.append(FieldCondition(key='course_name', match=MatchValue(value=course_name)))  # destination

    # Create a common list of doc_groups to match
    # doc_groups_to_match = doc_groups + public_doc_groups
    if doc_groups and 'All Documents' not in doc_groups:
      # Condition for matching any of the specified doc_groups
      match_any_condition = models.FieldCondition(key='doc_groups', match=models.MatchAny(any=doc_groups))
      combined_condition = models.Filter(should=[match_any_condition])

      # Add the combined condition to the must_conditions list
      must_conditions.append(combined_condition)

    must_not_conditions: list[models.Condition] = []

    if admin_disabled_doc_groups:
      # Condition for not matching any of the specified doc_groups
      must_not_conditions = [
          models.FieldCondition(key='doc_groups', match=models.MatchAny(any=admin_disabled_doc_groups))
      ]

    vector_search_filter = models.Filter(must=must_conditions, must_not=must_not_conditions, should=should_conditions)
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
