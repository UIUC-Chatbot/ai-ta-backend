import os
from typing import List

from injector import inject
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Qdrant
from qdrant_client import QdrantClient, models
from qdrant_client.conversions.common_types import WriteOrdering

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
    must_conditions = self._create_search_conditions(course_name, doc_groups)
    
    # Filter for the must_conditions
    myfilter = models.Filter(must=must_conditions)
    print(f"Filter: {myfilter}")
    
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
    """
    must_conditions: list[models.Condition] = [
        models.FieldCondition(key='course_name', match=models.MatchValue(value=course_name))
    ]
    
    if doc_groups and 'All Documents' not in doc_groups:
      # Final combined condition
      combined_condition = None
      # Condition for matching any of the specified doc_groups
      match_any_condition = models.FieldCondition(key='doc_groups', match=models.MatchAny(any=doc_groups))
      combined_condition = models.Filter(should=[match_any_condition])
      
      # Add the combined condition to the must_conditions list
      must_conditions.append(combined_condition)
    
    return must_conditions

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
  
  def add_document_groups_to_documents(self, course_name: str, documents: List[dict], doc_group_name: str):
    """
    Add document groups to documents in the vector database.
    """
    print(f"Adding document groups: {doc_group_name} to documents in the vector database for course: {course_name} and {len(documents)} documents.")
    update_operations = []
    for document in documents:
			# print(f"Adding document groups to document: {document} ")
      key = "url" if "url" in document else "s3_path"
      value = models.MatchValue(value=document[key])
      searchFilter = models.Filter(
				must=[
					models.FieldCondition(key="course_name", match=models.MatchValue(value=course_name)), 
					models.FieldCondition(key=key, 
																match=value)])
      
      payload = {
					"doc_groups": [group["name"] for group in document["doc_groups"]] + [doc_group_name],
			}
      
      # print(f"Updating to Payload: {payload}")
      
      update_operations.append(models.SetPayloadOperation(
				set_payload=models.SetPayload(
					payload=payload,
					filter=searchFilter
				),
			))

    print(f"update_operations for qdrant: {len(update_operations)}")
    result = self.qdrant_client.batch_update_points(
      collection_name=os.environ['QDRANT_COLLECTION_NAME'], 
      update_operations=update_operations, wait=False)
    return result