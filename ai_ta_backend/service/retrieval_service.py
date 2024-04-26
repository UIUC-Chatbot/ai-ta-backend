import inspect
import os
import time
import traceback
from typing import Dict, List, Union

import openai
import csv
from injector import inject
from langchain.chat_models import AzureChatOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.schema import Document

from ai_ta_backend.database.aws import AWSStorage
from ai_ta_backend.database.sql import SQLDatabase
from ai_ta_backend.database.vector import VectorDatabase
from ai_ta_backend.service.nomic_service import NomicService
from ai_ta_backend.service.posthog_service import PosthogService
from ai_ta_backend.service.sentry_service import SentryService
from ai_ta_backend.utils.utils_tokenization import count_tokens_and_cost


class RetrievalService:
  """
    Contains all methods for business logic of the retrieval service.
  """

  @inject
  def __init__(self, vdb: VectorDatabase, sqlDb: SQLDatabase, aws: AWSStorage, posthog: PosthogService,
               sentry: SentryService, nomicService: NomicService):
    self.vdb = vdb
    self.sqlDb = sqlDb
    self.aws = aws
    self.sentry = sentry
    self.posthog = posthog
    self.nomicService = nomicService

    openai.api_key = os.environ["OPENAI_API_KEY"]

    self.embeddings = OpenAIEmbeddings(
        model='text-embedding-ada-002',
        openai_api_base=os.environ["AZURE_OPENAI_ENDPOINT"],
        openai_api_type=os.environ['OPENAI_API_TYPE'],
        openai_api_key=os.environ["AZURE_OPENAI_KEY"],
        openai_api_version=os.environ["OPENAI_API_VERSION"],
    )

    self.llm = AzureChatOpenAI(
        temperature=0,
        deployment_name=os.environ["AZURE_OPENAI_ENGINE"],
        openai_api_base=os.environ["AZURE_OPENAI_ENDPOINT"],
        openai_api_key=os.environ["AZURE_OPENAI_KEY"],
        openai_api_version=os.environ["OPENAI_API_VERSION"],
        openai_api_type=os.environ['OPENAI_API_TYPE'],
    )

  def getTopContexts(self,
                     search_query: str,
                     course_name: str,
                     token_limit: int = 4_000,
                     doc_groups: List[str] | None = None) -> Union[List[Dict], str]:
    """Here's a summary of the work.

        /GET arguments
        course name (optional) str: A json response with TBD fields.

        Returns
        JSON: A json response with TBD fields. See main.py:getTopContexts docs.
        or
        String: An error message with traceback.
        """
    if doc_groups is None:
      doc_groups = []
    try:
      start_time_overall = time.monotonic()

      found_docs: list[Document] = self.vector_search(search_query=search_query,
                                                      course_name=course_name,
                                                      doc_groups=doc_groups)

      pre_prompt = "Please answer the following question. Use the context below, called your documents, only if it's helpful and don't use parts that are very irrelevant. It's good to quote from your documents directly, when you do always use Markdown footnotes for citations. Use react-markdown superscript to number the sources at the end of sentences (1, 2, 3...) and use react-markdown Footnotes to list the full document names for each number. Use ReactMarkdown aka 'react-markdown' formatting for super script citations, use semi-formal style. Feel free to say you don't know. \nHere's a few passages of the high quality documents:\n"
      # count tokens at start and end, then also count each context.
      token_counter, _ = count_tokens_and_cost(pre_prompt + "\n\nNow please respond to my query: " +  # type: ignore
                                               search_query)

      valid_docs = []
      num_tokens = 0
      for doc in found_docs:
        doc_string = f"Document: {doc.metadata['readable_filename']}{', page: ' + str(doc.metadata['pagenumber']) if doc.metadata['pagenumber'] else ''}\n{str(doc.page_content)}\n"
        num_tokens, prompt_cost = count_tokens_and_cost(doc_string)  # type: ignore

        print(
            f"tokens used/limit: {token_counter}/{token_limit}, tokens in chunk: {num_tokens}, total prompt cost (of these contexts): {prompt_cost}. 📄 File: {doc.metadata['readable_filename']}"
        )
        if token_counter + num_tokens <= token_limit:
          token_counter += num_tokens
          valid_docs.append(doc)
        else:
          # filled our token size, time to return
          break

      print(f"Total tokens used: {token_counter}. Docs used: {len(valid_docs)} of {len(found_docs)} docs retrieved")
      print(f"Course: {course_name} ||| search_query: {search_query}")
      print(f"⏰ ^^ Runtime of getTopContexts: {(time.monotonic() - start_time_overall):.2f} seconds")
      if len(valid_docs) == 0:
        return []

      self.posthog.capture(
          event_name="getTopContexts_success_DI",
          properties={
              "user_query": search_query,
              "course_name": course_name,
              "token_limit": token_limit,
              "total_tokens_used": token_counter,
              "total_contexts_used": len(valid_docs),
              "total_unique_docs_retrieved": len(found_docs),
              "getTopContext_total_latency_sec": time.monotonic() - start_time_overall,
          },
      )

      return self.format_for_json(valid_docs)
    except Exception as e:
      # return full traceback to front end
      # err: str = f"ERROR: In /getTopContexts. Course: {course_name} ||| search_query: {search_query}\nTraceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:\n{e}"  # type: ignore
      err: str = f"ERROR: In /getTopContexts. Course: {course_name} ||| search_query: {search_query}\nTraceback: {traceback.print_exc} \n{e}"  # type: ignore
      traceback.print_exc()
      print(err)
      self.sentry.capture_exception(e)
      return err

  def getAll(
      self,
      course_name: str,
  ):
    """Get all course materials based on course name.
    Args:
        course_name (as uploaded on supabase)
    Returns:
        list of dictionaries with distinct s3 path, readable_filename and course_name, url, base_url.
    """

    response = self.sqlDb.getAllMaterialsForCourse(course_name)

    data = response.data
    unique_combinations = set()
    distinct_dicts = []

    for item in data:
      combination = (item['s3_path'], item['readable_filename'], item['course_name'], item['url'], item['base_url'])
      if combination not in unique_combinations:
        unique_combinations.add(combination)
        distinct_dicts.append(item)

    return distinct_dicts

  def delete_data(self, course_name: str, s3_path: str, source_url: str):
    """Delete file from S3, Qdrant, and Supabase."""
    print(f"Deleting data for course {course_name}")
    # add delete from doc map logic here
    try:
      # Delete file from S3
      bucket_name = os.environ['S3_BUCKET_NAME']
      if bucket_name is None:
        raise ValueError("S3_BUCKET_NAME environment variable is not set")

      identifier_key, identifier_value = ("s3_path", s3_path) if s3_path else ("url", source_url)
      print(f"Deleting {identifier_value} from S3, Qdrant, and Supabase using {identifier_key}")

      # Delete from S3
      if identifier_key == "s3_path":
        self.delete_from_s3(bucket_name, s3_path)

      # Delete from Qdrant
      self.delete_from_qdrant(identifier_key, identifier_value)

      # Delete from Nomic and Supabase
      self.delete_from_nomic_and_supabase(course_name, identifier_key, identifier_value)

      return "Success"
    except Exception as e:
      err: str = f"ERROR IN delete_data: Traceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:{e}"  # type: ignore
      print(err)
      self.sentry.capture_exception(e)
      return err

  def delete_from_s3(self, bucket_name: str, s3_path: str):
    try:
      print("Deleting from S3")
      response = self.aws.delete_file(bucket_name, s3_path)
      print(f"AWS response: {response}")
    except Exception as e:
      print("Error in deleting file from s3:", e)
      self.sentry.capture_exception(e)

  def delete_from_qdrant(self, identifier_key: str, identifier_value: str):
    try:
      print("Deleting from Qdrant")
      response = self.vdb.delete_data(os.environ['QDRANT_COLLECTION_NAME'], identifier_key, identifier_value)
      print(f"Qdrant response: {response}")
    except Exception as e:
      if "timed out" in str(e):
        # Timed out is fine. Still deletes.
        pass
      else:
        print("Error in deleting file from Qdrant:", e)
        self.sentry.capture_exception(e)

  def getTopContextsWithMQR(self,
                            search_query: str,
                            course_name: str,
                            token_limit: int = 4_000) -> Union[List[Dict], str]:
    """
    New info-retrieval pipeline that uses multi-query retrieval + filtering + reciprocal rank fusion + context padding.
    1. Generate multiple queries based on the input search query.
    2. Retrieve relevant docs for each query.
    3. Filter the relevant docs based on the user query and pass them to the rank fusion step.
    4. [CANCELED BEC POINTLESS] Rank the docs based on the relevance score.
    5. Parent-doc-retrieval: Pad just the top 5 docs with expanded context from the original document.
    """
    raise NotImplementedError("Method deprecated for performance reasons. Hope to bring back soon.")

    # try:
    #   top_n_per_query = 40  # HARD CODE TO ENSURE WE HIT THE MAX TOKENS
    #   start_time_overall = time.monotonic()
    #   mq_start_time = time.monotonic()

    #   # 1. GENERATE MULTIPLE QUERIES
    #   generate_queries = (
    #       MULTI_QUERY_PROMPT | self.llm | StrOutputParser() | (lambda x: x.split("\n")) |
    #       (lambda x: list(filter(None, x)))  # filter out non-empty strings
    #   )

    #   generated_queries = generate_queries.invoke({"original_query": search_query})
    #   print("generated_queries", generated_queries)

    #   # 2. VECTOR SEARCH FOR EACH QUERY
    #   batch_found_docs_nested: list[list[Document]] = self.batch_vector_search(search_queries=generated_queries,
    #                                                                            course_name=course_name,
    #                                                                            top_n=top_n_per_query)

    #   # 3. RANK REMAINING DOCUMENTS -- good for parent doc padding of top 5 at the end.
    #   found_docs = self.reciprocal_rank_fusion(batch_found_docs_nested)
    #   found_docs = [doc for doc, score in found_docs]
    #   print(f"Num docs after re-ranking: {len(found_docs)}")
    #   if len(found_docs) == 0:
    #     return []
    #   print(f"⏰ Total multi-query processing runtime: {(time.monotonic() - mq_start_time):.2f} seconds")

    #   # 4. FILTER DOCS
    #   filtered_docs = filter_top_contexts(contexts=found_docs, user_query=search_query, timeout=30, max_concurrency=180)
    #   if len(filtered_docs) == 0:
    #     return []

    #   # 5. TOP DOC CONTEXT PADDING // parent document retriever
    #   final_docs = context_parent_doc_padding(filtered_docs, search_query, course_name)
    #   print(f"Number of final docs after context padding: {len(final_docs)}")

    #   pre_prompt = "Please answer the following question. Use the context below, called your documents, only if it's helpful and don't use parts that are very irrelevant. It's good to quote from your documents directly, when you do always use Markdown footnotes for citations. Use react-markdown superscript to number the sources at the end of sentences (1, 2, 3...) and use react-markdown Footnotes to list the full document names for each number. Use ReactMarkdown aka 'react-markdown' formatting for super script citations, use semi-formal style. Feel free to say you don't know. \nHere's a few passages of the high quality documents:\n"
    #   token_counter, _ = count_tokens_and_cost(pre_prompt + '\n\nNow please respond to my query: ' +
    #                                            search_query)  # type: ignore

    #   valid_docs = []
    #   num_tokens = 0
    #   for doc in final_docs:
    #     doc_string = f"Document: {doc['readable_filename']}{', page: ' + str(doc['pagenumber']) if doc['pagenumber'] else ''}\n{str(doc['text'])}\n"
    #     num_tokens, prompt_cost = count_tokens_and_cost(doc_string)  # type: ignore

    #     print(f"token_counter: {token_counter}, num_tokens: {num_tokens}, max_tokens: {token_limit}")
    #     if token_counter + num_tokens <= token_limit:
    #       token_counter += num_tokens
    #       valid_docs.append(doc)
    #     else:
    #       # filled our token size, time to return
    #       break

    #   print(f"Total tokens used: {token_counter} Used {len(valid_docs)} of total unique docs {len(found_docs)}.")
    #   print(f"Course: {course_name} ||| search_query: {search_query}")
    #   print(f"⏰ ^^ Runtime of getTopContextsWithMQR: {(time.monotonic() - start_time_overall):.2f} seconds")

    #   if len(valid_docs) == 0:
    #     return []

    #   self.posthog.capture('distinct_id_of_the_user',
    #                        event='filter_top_contexts_succeeded',
    #                        properties={
    #                            'user_query': search_query,
    #                            'course_name': course_name,
    #                            'token_limit': token_limit,
    #                            'total_tokens_used': token_counter,
    #                            'total_contexts_used': len(valid_docs),
    #                            'total_unique_docs_retrieved': len(found_docs),
    #                        })

    #   return self.format_for_json_mqr(valid_docs)
    # except Exception as e:
    #   # return full traceback to front end
    #   err: str = f"ERROR: In /getTopContextsWithMQR. Course: {course_name} ||| search_query: {search_query}\nTraceback: {traceback.format_exc()}❌❌ Error in {inspect.currentframe().f_code.co_name}:\n{e}"  # type: ignore
    #   print(err)
    #   sentry_sdk.capture_exception(e)
    #   return err

  def format_for_json_mqr(self, found_docs) -> List[Dict]:
    """
    Same as format_for_json, but for the new MQR pipeline.
    """
    for found_doc in found_docs:
      if "pagenumber" not in found_doc.keys():
        print("found no pagenumber")
        found_doc['pagenumber'] = found_doc['pagenumber_or_timestamp']

    contexts = [
        {
            'text': doc['text'],
            'readable_filename': doc['readable_filename'],
            'course_name ': doc['course_name'],
            's3_path': doc['s3_path'],
            'pagenumber': doc['pagenumber'],
            'url': doc['url'],  # wouldn't this error out?
            'base_url': doc['base_url'],
        } for doc in found_docs
    ]

    return contexts

  def delete_from_nomic_and_supabase(self, course_name: str, identifier_key: str, identifier_value: str):
    try:
      print(f"Nomic delete. Course: {course_name} using {identifier_key}: {identifier_value}")
      response = self.sqlDb.getMaterialsForCourseAndKeyAndValue(course_name, identifier_key, identifier_value)
      if not response.data:
        raise Exception(f"No materials found for {course_name} using {identifier_key}: {identifier_value}")
      data = response.data[0]  # single record fetched
      nomic_ids_to_delete = [str(data['id']) + "_" + str(i) for i in range(1, len(data['contexts']) + 1)]

      # delete from Nomic
      response = self.sqlDb.getProjectsMapForCourse(course_name)
      if not response.data:
        raise Exception(f"No document map found for this course: {course_name}")
      project_id = response.data[0]['doc_map_id']
      self.nomicService.delete_from_document_map(project_id, nomic_ids_to_delete)
    except Exception as e:
      print(f"Nomic Error in deleting. {identifier_key}: {identifier_value}", e)
      self.sentry.capture_exception(e)

    try:
      print(f"Supabase Delete. course: {course_name} using {identifier_key}: {identifier_value}")
      response = self.sqlDb.deleteMaterialsForCourseAndKeyAndValue(course_name, identifier_key, identifier_value)
    except Exception as e:
      print(f"Supabase Error in delete. {identifier_key}: {identifier_value}", e)
      self.sentry.capture_exception(e)

  def vector_search(self, search_query, course_name, doc_groups: List[str] | None = None):
    """
    Search the vector database for a given query, course name, and document groups.
    """
    # Return empty list if no search query is provided
    if doc_groups is None:
      doc_groups = []
    # Max number of search results to return
    top_n = 80
    # Embed the user query and measure the latency
    user_query_embedding = self._embed_query_and_measure_latency(search_query)
    # Capture the search invoked event to PostHog
    self._capture_search_invoked_event(search_query, course_name, doc_groups)
    # Perform the vector search
    search_results = self._perform_vector_search(search_query, course_name, doc_groups, user_query_embedding, top_n)
    # Process the search results by extracting the page content and metadata
    found_docs = self._process_search_results(search_results, course_name)
    # Capture the search succeeded event to PostHog with the vector scores
    self._capture_search_succeeded_event(search_query, course_name, search_results)
    return found_docs

  def _embed_query_and_measure_latency(self, search_query):
    openai_start_time = time.monotonic()
    user_query_embedding = self.embeddings.embed_query(search_query)
    self.openai_embedding_latency = time.monotonic() - openai_start_time
    return user_query_embedding

  def _capture_search_invoked_event(self, search_query, course_name, doc_groups):
    self.posthog.capture(
        event_name="vector_search_invoked",
        properties={
            "user_query": search_query,
            "course_name": course_name,
            "doc_groups": doc_groups,
        },
    )

  def _perform_vector_search(self, search_query, course_name, doc_groups, user_query_embedding, top_n):
    qdrant_start_time = time.monotonic()
    search_results = self.vdb.vector_search(search_query, course_name, doc_groups, user_query_embedding, top_n)
    self.qdrant_latency_sec = time.monotonic() - qdrant_start_time
    return search_results

  def _process_search_results(self, search_results, course_name):
    found_docs: list[Document] = []
    for d in search_results:
      try:
        metadata = d.payload
        page_content = metadata["page_content"]
        del metadata["page_content"]
        if "pagenumber" not in metadata.keys() and "pagenumber_or_timestamp" in metadata.keys():
          metadata["pagenumber"] = metadata["pagenumber_or_timestamp"]

        found_docs.append(Document(page_content=page_content, metadata=metadata))
      except Exception as e:
        print(f"Error in vector_search(), for course: `{course_name}`. Error: {e}")
        self.sentry.capture_exception(e)
    return found_docs

  def _capture_search_succeeded_event(self, search_query, course_name, search_results):
    vector_score_calc_latency_sec = time.monotonic()
    max_vector_score, min_vector_score, avg_vector_score = self._calculate_vector_scores(search_results)
    self.posthog.capture(
        event_name="vector_search_succeeded",
        properties={
            "user_query": search_query,
            "course_name": course_name,
            "qdrant_latency_sec": self.qdrant_latency_sec,
            "openai_embedding_latency_sec": self.openai_embedding_latency,
            "max_vector_score": max_vector_score,
            "min_vector_score": min_vector_score,
            "avg_vector_score": avg_vector_score,
            "vector_score_calculation_latency_sec": time.monotonic() - vector_score_calc_latency_sec,  
        },
    )

  def _calculate_vector_scores(self, search_results):
    max_vector_score = 0
    min_vector_score = 0
    total_vector_score = 0
    for result in search_results:
      max_vector_score = max(max_vector_score, result.score)
      min_vector_score = min(min_vector_score, result.score)
      total_vector_score += result.score
    avg_vector_score = total_vector_score / len(search_results) if search_results else 0
    return max_vector_score, min_vector_score, avg_vector_score

  def format_for_json(self, found_docs: List[Document]) -> List[Dict]:
    """Formatting only.
        {'course_name': course_name, 'contexts': [{'source_name': 'Lumetta_notes', 'source_location': 'pg. 19', 'text': 'In FSM, we do this...'}, {'source_name': 'Lumetta_notes', 'source_location': 'pg. 20', 'text': 'In Assembly language, the code does that...'},]}

        Args:
            found_docs (List[Document]): _description_

        Raises:
            Exception: _description_

        Returns:
            List[Dict]: _description_
        """
    for found_doc in found_docs:
      if "pagenumber" not in found_doc.metadata.keys():
        print("found no pagenumber")
        found_doc.metadata["pagenumber"] = found_doc.metadata["pagenumber_or_timestamp"]

    contexts = [
        {
            "text": doc.page_content,
            "readable_filename": doc.metadata["readable_filename"],
            "course_name ": doc.metadata["course_name"],
            "s3_path": doc.metadata["s3_path"],
            "pagenumber": doc.metadata["pagenumber"],  # this because vector db schema is older...
            # OPTIONAL PARAMS...
            "url": doc.metadata.get("url"),  # wouldn't this error out?
            "base_url": doc.metadata.get("base_url"),
        } for doc in found_docs
    ]

    return contexts
  
  def insertDocumentGroups(self, course_name, csv_path):
    """
    Inserts document groups and documents into the database based on the CSV mapping.
    Additionally, saves doc group name along with the entire document info in the output csv file.
    """
    urls = []
    doc_group_count = 0
    # Count of documents in all document groups
    docs_doc_groups_count = 0
    # Fetch existing documents by URLs from CSV
    with open(csv_path, newline='') as csvfile:
        for row in csv.DictReader(csvfile):
            urls = eval(row['start_urls'])
            doc_group_name = row['university']
            # Count of documents in the document group
            docs_doc_group_count = 0
            # print(f"fetching existing documents for course_name: {course_name} and URLs: {urls}")
            page = 1
            while True:
                print(f"fetching page: {page} for doc_group: {doc_group_name}, with urls: {urls}")
                existing_documents_response = self.sqlDb.fetchDocumentsByURLs(urls, course_name, page)
                existing_documents = existing_documents_response.data
                if not existing_documents:
                    break  # Exit loop if no more documents are returned
                
                # Process documents in batches here
                document_group = {'name': doc_group_name, 'course_name': course_name}
                documents_to_update = existing_documents

                print("Document groups for insertion: ", document_group)
                print("Documents for update: ", len(documents_to_update))
                
                docs_doc_groups_count += len(documents_to_update)
                docs_doc_group_count += len(documents_to_update)

                doc_group_id = self.sqlDb.insertDocumentGroupsBulk(document_group)

                # Bulk update
                self.sqlDb.updateDocumentsDocGroupsBulk(documents_to_update, doc_group_id)
                
                page += 1  # Move to the next page

                # Output to CSV is handled outside the pagination loop
                with open('updated_documents.csv', newline='', mode='a') as output_csvfile:
                    writer = csv.writer(output_csvfile)
                    for doc in documents_to_update:
                        writer.writerow([document_group['name']] + list(doc.values()))

            with open('doc_groups.csv', newline='', mode='a') as output_csvfile:
                writer = csv.writer(output_csvfile)
                writer.writerow([doc_group_name, docs_doc_group_count])
              
            doc_group_count += 1

    return doc_group_count, docs_doc_groups_count
