import asyncio
import inspect
import os
import time
import traceback
from typing import Dict, List, Union

import boto3
import openai
import sentry_sdk
import supabase
from langchain import hub
from langchain.chat_models import AzureChatOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.load import dumps, loads
from langchain.schema import Document
from langchain.schema.output_parser import StrOutputParser
from langchain.vectorstores import Qdrant
from posthog import Posthog
from qdrant_client import QdrantClient, models

from ai_ta_backend.context_parent_doc_padding import context_parent_doc_padding
from ai_ta_backend.extreme_context_stuffing import OpenAIAPIProcessor

# from ai_ta_backend.filtering_contexts import filter_top_contexts
from ai_ta_backend.nomic_logging import delete_from_document_map
from ai_ta_backend.utils_tokenization import count_tokens_and_cost

MULTI_QUERY_PROMPT = hub.pull("langchain-ai/rag-fusion-query-generation")
OPENAI_API_TYPE = "azure"  # "openai" or "azure"


class Ingest():
  """
  Contains all methods for building and using vector databases.
  """

  def __init__(self):
    """
    Initialize AWS S3, Qdrant, and Supabase.
    """
    openai.api_key = os.getenv("OPENAI_API_KEY")

    # vector DB
    self.qdrant_client = QdrantClient(
        url=os.getenv('QDRANT_URL'),
        api_key=os.getenv('QDRANT_API_KEY'),
    )

    self.vectorstore = Qdrant(client=self.qdrant_client,
                              collection_name=os.environ['QDRANT_COLLECTION_NAME'],
                              embeddings=OpenAIEmbeddings(openai_api_type=OPENAI_API_TYPE))

    # S3
    self.s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    )

    # Create a Supabase client
    self.supabase_client = supabase.create_client(  # type: ignore
        supabase_url=os.environ['SUPABASE_URL'], supabase_key=os.environ['SUPABASE_API_KEY'])

    self.llm = AzureChatOpenAI(
        temperature=0,
        deployment_name=os.getenv('AZURE_OPENAI_ENGINE'),  #type:ignore
        openai_api_base=os.getenv('AZURE_OPENAI_ENDPOINT'),  #type:ignore
        openai_api_key=os.getenv('AZURE_OPENAI_KEY'),  #type:ignore
        openai_api_version=os.getenv('OPENAI_API_VERSION'),  #type:ignore
        openai_api_type=OPENAI_API_TYPE)

    self.posthog = Posthog(sync_mode=True,
                           project_api_key=os.environ['POSTHOG_API_KEY'],
                           host='https://app.posthog.com')

    return None

  def __del__(self):
    # Gracefully shutdown the Posthog client -- this was a main cause of dangling threads.
    # Since I changed Posthog to be sync, no need to shutdown.
    # try:
    #   self.posthog.shutdown()
    # except Exception as e:
    #   print("Failed to shutdown PostHog. Probably fine. Error: ", e)
    try:
      self.qdrant_client.close()
    except Exception as e:
      print("Failed to shutdown Qdrant. Probably fine. Error: ", e)
    try:
      del self.supabase_client
    except Exception as e:
      print("Failed delete supabase_client. Probably fine. Error: ", e)
    try:
      del self.s3_client
    except Exception as e:
      print("Failed to delete s3_client. Probably fine. Error: ", e)

  def delete_entire_course(self, course_name: str):
    """Delete entire course.

    Delete materials from S3, Supabase SQL, Vercel KV, and QDrant vector DB
    Args:
        course_name (str): _description_
    """
    print(f"Deleting entire course: {course_name}")
    try:
      # Delete file from S3
      print("Deleting from S3")
      objects_to_delete = self.s3_client.list_objects(Bucket=os.getenv('S3_BUCKET_NAME'),
                                                      Prefix=f'courses/{course_name}/')
      for object in objects_to_delete['Contents']:
        self.s3_client.delete_object(Bucket=os.getenv('S3_BUCKET_NAME'), Key=object['Key'])
    except Exception as e:
      err: str = f"ERROR IN delete_entire_course(): Traceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:{e}"  # type: ignore
      print(err)
      sentry_sdk.capture_exception(e)
      pass

    try:
      # Delete from Qdrant
      # docs for nested keys: https://qdrant.tech/documentation/concepts/filtering/#nested-key
      # Qdrant "points" look like this: Record(id='000295ca-bd28-ac4a-6f8d-c245f7377f90', payload={'metadata': {'course_name': 'zotero-extreme', 'pagenumber_or_timestamp': 15, 'readable_filename': 'Dunlosky et al. - 2013 - Improving Students’ Learning With Effective Learni.pdf', 's3_path': 'courses/zotero-extreme/Dunlosky et al. - 2013 - Improving Students’ Learning With Effective Learni.pdf'}, 'page_content': '18  \nDunlosky et al.\n3.3 Effects in representative educational contexts. Sev-\neral of the large summarization-training studies have been \nconducted in regular classrooms, indicating the feasibility of \ndoing so. For example, the study by A. King (1992) took place \nin the context of a remedial study-skills course for undergrad-\nuates, and the study by Rinehart et al. (1986) took place in \nsixth-grade classrooms, with the instruction led by students \nregular teachers. In these and other cases, students benefited \nfrom the classroom training. We suspect it may actually be \nmore feasible to conduct these kinds of training studies in \nclassrooms than in the laboratory, given the nature of the time \ncommitment for students. Even some of the studies that did \nnot involve training were conducted outside the laboratory; for \nexample, in the Bednall and Kehoe (2011) study on learning \nabout logical fallacies from Web modules (see data in Table 3), \nthe modules were actually completed as a homework assign-\nment. Overall, benefits can be observed in classroom settings; \nthe real constraint is whether students have the skill to suc-\ncessfully summarize, not whether summarization occurs in the \nlab or the classroom.\n3.4 Issues for implementation. Summarization would be \nfeasible for undergraduates or other learners who already \nknow how to summarize. For these students, summarization \nwould constitute an easy-to-implement technique that would \nnot take a lot of time to complete or understand. The only \nconcern would be whether these students might be better \nserved by some other strategy, but certainly summarization \nwould be better than the study strategies students typically \nfavor, such as highlighting and rereading (as we discuss in the \nsections on those strategies below). A trickier issue would \nconcern implementing the strategy with students who are not \nskilled summarizers. Relatively intensive training programs \nare required for middle school students or learners with learn-\ning disabilities to benefit from summarization. Such efforts \nare not misplaced; training has been shown to benefit perfor-\nmance on a range of measures, although the training proce-\ndures do raise practical issues (e.g., Gajria & Salvia, 1992: \n6.511 hours of training used for sixth through ninth graders \nwith learning disabilities; Malone & Mastropieri, 1991: 2 \ndays of training used for middle school students with learning \ndisabilities; Rinehart et al., 1986: 4550 minutes of instruc-\ntion per day for 5 days used for sixth graders). Of course, \ninstructors may want students to summarize material because \nsummarization itself is a goal, not because they plan to use \nsummarization as a study technique, and that goal may merit \nthe efforts of training.\nHowever, if the goal is to use summarization as a study \ntechnique, our question is whether training students would be \nworth the amount of time it would take, both in terms of the \ntime required on the part of the instructor and in terms of the \ntime taken away from students other activities. For instance, \nin terms of efficacy, summarization tends to fall in the middle \nof the pack when compared to other techniques. In direct \ncomparisons, it was sometimes more useful than rereading \n(Rewey, Dansereau, & Peel, 1991) and was as useful as note-\ntaking (e.g., Bretzing & Kulhavy, 1979) but was less powerful \nthan generating explanations (e.g., Bednall & Kehoe, 2011) or \nself-questioning (A. King, 1992).\n3.5 Summarization: Overall assessment. On the basis of the \navailable evidence, we rate summarization as low utility. It can \nbe an effective learning strategy for learners who are already \nskilled at summarizing; however, many learners (including \nchildren, high school students, and even some undergraduates) \nwill require extensive training, which makes this strategy less \nfeasible. Our enthusiasm is further dampened by mixed find-\nings regarding which tasks summarization actually helps. \nAlthough summarization has been examined with a wide \nrange of text materials, many researchers have pointed to fac-\ntors of these texts that seem likely to moderate the effects of \nsummarization (e.g'}, vector=None),
      print("deleting from qdrant")
      self.qdrant_client.delete(
          collection_name=os.environ['QDRANT_COLLECTION_NAME'],
          points_selector=models.Filter(must=[
              models.FieldCondition(
                  key="course_name",
                  match=models.MatchValue(value=course_name),
              ),
          ]),
      )
    except Exception as e:
      err: str = f"ERROR IN delete_entire_course(): Traceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:{e}"  # type: ignore
      print(err)
      sentry_sdk.capture_exception(e)
      pass

    try:
      # Delete from Supabase
      print("deleting from supabase")
      response = self.supabase_client.from_(os.environ['NEW_NEW_NEWNEW_MATERIALS_SUPABASE_TABLE']).delete().eq(
          'course_name', course_name).execute()
      print("supabase response: ", response)
      return "Success"
    except Exception as e:
      err: str = f"ERROR IN delete_entire_course(): Traceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:{e}"  # type: ignore
      print(err)
      sentry_sdk.capture_exception(e)
    # todo: delete from Vercel KV to fully make the coure not exist. Last db to delete from (as of now, Aug 15)

  def delete_data(self, course_name: str, s3_path: str, source_url: str):
    """Delete file from S3, Qdrant, and Supabase."""
    print(f"Deleting {s3_path} from S3, Qdrant, and Supabase for course {course_name}")
    # add delete from doc map logic here
    try:
      # Delete file from S3
      bucket_name = os.getenv('S3_BUCKET_NAME')

      # Delete files by S3 path
      if s3_path:
        try:
          self.s3_client.delete_object(Bucket=bucket_name, Key=s3_path)
        except Exception as e:
          print("Error in deleting file from s3:", e)
          sentry_sdk.capture_exception(e)
        # Delete from Qdrant
        # docs for nested keys: https://qdrant.tech/documentation/concepts/filtering/#nested-key
        # Qdrant "points" look like this: Record(id='000295ca-bd28-ac4a-6f8d-c245f7377f90', payload={'metadata': {'course_name': 'zotero-extreme', 'pagenumber_or_timestamp': 15, 'readable_filename': 'Dunlosky et al. - 2013 - Improving Students’ Learning With Effective Learni.pdf', 's3_path': 'courses/zotero-extreme/Dunlosky et al. - 2013 - Improving Students’ Learning With Effective Learni.pdf'}, 'page_content': '18  \nDunlosky et al.\n3.3 Effects in representative educational contexts. Sev-\neral of the large summarization-training studies have been \nconducted in regular classrooms, indicating the feasibility of \ndoing so. For example, the study by A. King (1992) took place \nin the context of a remedial study-skills course for undergrad-\nuates, and the study by Rinehart et al. (1986) took place in \nsixth-grade classrooms, with the instruction led by students \nregular teachers. In these and other cases, students benefited \nfrom the classroom training. We suspect it may actually be \nmore feasible to conduct these kinds of training  ...
        try:
          self.qdrant_client.delete(
              collection_name=os.environ['QDRANT_COLLECTION_NAME'],
              points_selector=models.Filter(must=[
                  models.FieldCondition(
                      key="s3_path",
                      match=models.MatchValue(value=s3_path),
                  ),
              ]),
          )
        except Exception as e:
          if "timed out" in str(e):
            # Timed out is fine. Still deletes.
            # https://github.com/qdrant/qdrant/issues/3654#issuecomment-1955074525
            pass
          else:
            print("Error in deleting file from Qdrant:", e)
            sentry_sdk.capture_exception(e)
        try:
          # delete from Nomic
          response = self.supabase_client.from_(
              os.environ['NEW_NEW_NEWNEW_MATERIALS_SUPABASE_TABLE']).select("id, s3_path, contexts").eq(
                  's3_path', s3_path).eq('course_name', course_name).execute()
          data = response.data[0]  #single record fetched
          nomic_ids_to_delete = []
          context_count = len(data['contexts'])
          for i in range(1, context_count + 1):
            nomic_ids_to_delete.append(str(data['id']) + "_" + str(i))

          # delete from Nomic
          res = delete_from_document_map(course_name, nomic_ids_to_delete)
        except Exception as e:
          print("Error in deleting file from Nomic:", e)
          sentry_sdk.capture_exception(e)

        try:
          self.supabase_client.from_(os.environ['NEW_NEW_NEWNEW_MATERIALS_SUPABASE_TABLE']).delete().eq(
              's3_path', s3_path).eq('course_name', course_name).execute()
        except Exception as e:
          print("Error in deleting file from supabase:", e)
          sentry_sdk.capture_exception(e)

      # Delete files by their URL identifier
      elif source_url:
        try:
          # Delete from Qdrant
          self.qdrant_client.delete(
              collection_name=os.environ['QDRANT_COLLECTION_NAME'],
              points_selector=models.Filter(must=[
                  models.FieldCondition(
                      key="url",
                      match=models.MatchValue(value=source_url),
                  ),
              ]),
          )
        except Exception as e:
          if "timed out" in str(e):
            # Timed out is fine. Still deletes.
            # https://github.com/qdrant/qdrant/issues/3654#issuecomment-1955074525
            pass
          else:
            print("Error in deleting file from Qdrant:", e)
            sentry_sdk.capture_exception(e)
        try:
          # delete from Nomic
          response = self.supabase_client.from_(
              os.environ['NEW_NEW_NEWNEW_MATERIALS_SUPABASE_TABLE']).select("id, url, contexts").eq(
                  'url', source_url).eq('course_name', course_name).execute()
          data = response.data[0]  #single record fetched
          nomic_ids_to_delete = []
          context_count = len(data['contexts'])
          for i in range(1, context_count + 1):
            nomic_ids_to_delete.append(str(data['id']) + "_" + str(i))

          # delete from Nomic
          res = delete_from_document_map(course_name, nomic_ids_to_delete)
        except Exception as e:
          print("Error in deleting file from Nomic:", e)
          sentry_sdk.capture_exception(e)

        try:
          # delete from Supabase
          self.supabase_client.from_(os.environ['NEW_NEW_NEWNEW_MATERIALS_SUPABASE_TABLE']).delete().eq(
              'url', source_url).eq('course_name', course_name).execute()
        except Exception as e:
          print("Error in deleting file from supabase:", e)
          sentry_sdk.capture_exception(e)

      # Delete from Supabase
      return "Success"
    except Exception as e:
      err: str = f"ERROR IN delete_data: Traceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:{e}"  # type: ignore
      print(err)
      sentry_sdk.capture_exception(e)
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

    response = self.supabase_client.table(os.environ['NEW_NEW_NEWNEW_MATERIALS_SUPABASE_TABLE']).select(
        'course_name, s3_path, readable_filename, url, base_url').eq('course_name', course_name).execute()

    data = response.data
    unique_combinations = set()
    distinct_dicts = []

    for item in data:
      combination = (item['s3_path'], item['readable_filename'], item['course_name'], item['url'], item['base_url'])
      if combination not in unique_combinations:
        unique_combinations.add(combination)
        distinct_dicts.append(item)

    return distinct_dicts

  def vector_search(self, search_query, course_name):
    top_n = 80
    # EMBED
    openai_start_time = time.monotonic()
    o = OpenAIEmbeddings(openai_api_type=OPENAI_API_TYPE)
    user_query_embedding = o.embed_query(search_query)
    openai_embedding_latency = time.monotonic() - openai_start_time

    # SEARCH
    myfilter = models.Filter(must=[
        models.FieldCondition(key='course_name', match=models.MatchValue(value=course_name)),
    ])
    self.posthog.capture('distinct_id_of_the_user',
                         event='vector_search_invoked',
                         properties={
                             'user_query': search_query,
                             'course_name': course_name,
                         })
    qdrant_start_time = time.monotonic()
    search_results = self.qdrant_client.search(
        collection_name=os.environ['QDRANT_COLLECTION_NAME'],
        query_filter=myfilter,
        with_vectors=False,
        query_vector=user_query_embedding,
        limit=top_n,  # Return n closest points

        # In a system with high disk latency, the re-scoring step may become a bottleneck: https://qdrant.tech/documentation/guides/quantization/
        search_params=models.SearchParams(quantization=models.QuantizationSearchParams(rescore=False)))

    found_docs: list[Document] = []
    for d in search_results:
      try:
        metadata = d.payload
        page_content = metadata['page_content']
        del metadata['page_content']
        if "pagenumber" not in metadata.keys() and "pagenumber_or_timestamp" in metadata.keys():  # type: ignore
          # aiding in the database migration...
          metadata["pagenumber"] = metadata["pagenumber_or_timestamp"]  # type: ignore

        found_docs.append(Document(page_content=page_content, metadata=metadata))  # type: ignore
      except Exception as e:
        print(f"Error in vector_search(), for course: `{course_name}`. Error: {e}")
        sentry_sdk.capture_exception(e)

    self.posthog.capture('distinct_id_of_the_user',
                         event='vector_search_succeded',
                         properties={
                             'user_query': search_query,
                             'course_name': course_name,
                             'qdrant_latency_sec': time.monotonic() - qdrant_start_time,
                             'openai_embedding_latency_sec': openai_embedding_latency
                         })
    # print("found_docs", found_docs)
    return found_docs

  def getTopContexts(self, search_query: str, course_name: str, token_limit: int = 4_000) -> Union[List[Dict], str]:
    """Here's a summary of the work.

    /GET arguments
      course name (optional) str: A json response with TBD fields.

    Returns
      JSON: A json response with TBD fields. See main.py:getTopContexts docs.
      or
      String: An error message with traceback.
    """
    try:
      start_time_overall = time.monotonic()

      found_docs: list[Document] = self.vector_search(search_query=search_query, course_name=course_name)

      pre_prompt = "Please answer the following question. Use the context below, called your documents, only if it's helpful and don't use parts that are very irrelevant. It's good to quote from your documents directly, when you do always use Markdown footnotes for citations. Use react-markdown superscript to number the sources at the end of sentences (1, 2, 3...) and use react-markdown Footnotes to list the full document names for each number. Use ReactMarkdown aka 'react-markdown' formatting for super script citations, use semi-formal style. Feel free to say you don't know. \nHere's a few passages of the high quality documents:\n"
      # count tokens at start and end, then also count each context.
      token_counter, _ = count_tokens_and_cost(pre_prompt + '\n\nNow please respond to my query: ' +
                                               search_query)  # type: ignore

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

      self.posthog.capture('distinct_id_of_the_user',
                           event='success_get_top_contexts_OG',
                           properties={
                               'user_query': search_query,
                               'course_name': course_name,
                               'token_limit': token_limit,
                               'total_tokens_used': token_counter,
                               'total_contexts_used': len(valid_docs),
                               'total_unique_docs_retrieved': len(found_docs),
                               'getTopContext_total_latency_sec': time.monotonic() - start_time_overall,
                           })

      return self.format_for_json(valid_docs)
    except Exception as e:
      # return full traceback to front end
      err: str = f"ERROR: In /getTopContexts. Course: {course_name} ||| search_query: {search_query}\nTraceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:\n{e}"  # type: ignore
      print(err)
      sentry_sdk.capture_exception(e)
      return err

  def batch_vector_search(self, search_queries: List[str], course_name: str, top_n: int = 50):
    """
    Perform a similarity search for all the generated queries at once.
    """
    start_time = time.monotonic()

    from qdrant_client.http import models as rest
    o = OpenAIEmbeddings(openai_api_type=OPENAI_API_TYPE)
    # Prepare the filter for the course name
    myfilter = rest.Filter(must=[
        rest.FieldCondition(key='course_name', match=rest.MatchValue(value=course_name)),
    ])

    # Prepare the search requests
    search_requests = []
    for query in search_queries:
      user_query_embedding = o.embed_query(query)
      search_requests.append(
          rest.SearchRequest(vector=user_query_embedding,
                             filter=myfilter,
                             limit=top_n,
                             with_payload=True,
                             params=models.SearchParams(quantization=models.QuantizationSearchParams(rescore=False))))

    # Perform the batch search
    search_results = self.qdrant_client.search_batch(
        collection_name=os.environ['QDRANT_COLLECTION_NAME'],
        requests=search_requests,
    )
    # process search results
    found_docs: list[list[Document]] = []
    for result in search_results:
      docs = []
      for doc in result:
        try:
          metadata = doc.payload
          page_content = metadata['page_content']
          del metadata['page_content']

          if "pagenumber" not in metadata.keys() and "pagenumber_or_timestamp" in metadata.keys():
            metadata["pagenumber"] = metadata["pagenumber_or_timestamp"]

          docs.append(Document(page_content=page_content, metadata=metadata))
        except Exception:
          print(traceback.print_exc())
      found_docs.append(docs)

    print(f"⏰ Qdrant Batch Search runtime: {(time.monotonic() - start_time):.2f} seconds")
    return found_docs

  def reciprocal_rank_fusion(self, results: list[list], k=60):
    """
      Since we have multiple queries, and n documents returned per query, we need to go through all the results
      and collect the documents with the highest overall score, as scored by qdrant similarity matching.
      """
    fused_scores = {}
    count = 0
    unique_count = 0
    for docs in results:
      # Assumes the docs are returned in sorted order of relevance
      count += len(docs)
      for rank, doc in enumerate(docs):
        doc_str = dumps(doc)
        if doc_str not in fused_scores:
          fused_scores[doc_str] = 0
          unique_count += 1
        fused_scores[doc_str] += 1 / (rank + k)
        # Uncomment for debugging
        # previous_score = fused_scores[doc_str]
        #print(f"Change score for doc: {doc_str}, previous score: {previous_score}, updated score: {fused_scores[doc_str]} ")
    print(f"Total number of documents in rank fusion: {count}")
    print(f"Total number of unique documents in rank fusion: {unique_count}")
    reranked_results = [
        (loads(doc), score) for doc, score in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
    ]
    return reranked_results

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
    return 'fail'

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

  def get_context_stuffed_prompt(self, user_question: str, course_name: str, top_n: int, top_k_to_search: int) -> str:
    """
    Get a stuffed prompt for a given user question and course name.
    Args:
      user_question (str)
      course_name (str) : used for metadata filtering
    Returns : str
      a very long "stuffed prompt" with question + summaries of top_n most relevant documents.
    """
    # MMR with metadata filtering based on course_name
    vec_start_time = time.monotonic()
    found_docs = self.vectorstore.max_marginal_relevance_search(user_question, k=top_n, fetch_k=top_k_to_search)
    print(
        f"⏰ MMR Search runtime (top_n_to_keep: {top_n}, top_k_to_search: {top_k_to_search}): {(time.monotonic() - vec_start_time):.2f} seconds"
    )

    requests = []
    for doc in found_docs:
      print("doc", doc)
      dictionary = {
          "model": "gpt-3.5-turbo",
          "messages": [{
              "role":
                  "system",
              "content":
                  "You are a factual summarizer of partial documents. Stick to the facts (including partial info when necessary to avoid making up potentially incorrect details), and say I don't know when necessary."
          }, {
              "role":
                  "user",
              "content":
                  f"Provide a comprehensive summary of the given text, based on this question:\n{doc.page_content}\nQuestion: {user_question}\nThe summary should cover all the key points that are relevant to the question, while also condensing the information into a concise format. The length of the summary should be as short as possible, without losing relevant information.\nMake use of direct quotes from the text.\nFeel free to include references, sentence fragments, keywords or anything that could help someone learn about it, only as it relates to the given question.\nIf the text does not provide information to answer the question, please write 'None' and nothing else.",
          }],
          "n": 1,
          "max_tokens": 600,
          "metadata": doc.metadata
      }
      requests.append(dictionary)

    oai = OpenAIAPIProcessor(
        input_prompts_list=requests,
        request_url='https://api.openai.com/v1/chat/completions',
        api_key=os.getenv("OPENAI_API_KEY"),
        max_requests_per_minute=1500,
        max_tokens_per_minute=90000,
        token_encoding_name='cl100k_base',  # nosec -- reasonable bandit error suppression
        max_attempts=5,
        logging_level=20)

    chain_start_time = time.monotonic()
    asyncio.run(oai.process_api_requests_from_file())
    results: list[str] = oai.results
    print(f"⏰ EXTREME context stuffing runtime: {(time.monotonic() - chain_start_time):.2f} seconds")

    print(f"Cleaned results: {oai.cleaned_results}")

    all_texts = ""
    separator = '---'  # between each context
    token_counter = 0  #keeps track of tokens in each summarization
    max_tokens = 7_500  #limit, will keep adding text to string until 8000 tokens reached.
    for i, text in enumerate(oai.cleaned_results):
      if text.lower().startswith('none') or text.lower().endswith('none.') or text.lower().endswith('none'):
        # no useful text, it replied with a summary of "None"
        continue
      if text is not None:
        if "pagenumber" not in results[i][-1].keys():  # type: ignore
          results[i][-1]['pagenumber'] = results[i][-1].get('pagenumber_or_timestamp')  # type: ignore
        num_tokens, prompt_cost = count_tokens_and_cost(text)  # type: ignore
        if token_counter + num_tokens > max_tokens:
          print(f"Total tokens yet in loop {i} is {num_tokens}")
          break  # Stop building the string if it exceeds the maximum number of tokens
        token_counter += num_tokens
        filename = str(results[i][-1].get('readable_filename', ''))  # type: ignore
        pagenumber_or_timestamp = str(results[i][-1].get('pagenumber', ''))  # type: ignore
        pagenumber = f", page: {pagenumber_or_timestamp}" if pagenumber_or_timestamp else ''
        doc = f"Document : filename: {filename}" + pagenumber
        summary = f"\nSummary: {text}"
        all_texts += doc + summary + '\n' + separator + '\n'

    stuffed_prompt = """Please answer the following question.
Use the context below, called 'your documents', only if it's helpful and don't use parts that are very irrelevant.
It's good to quote 'your documents' directly using informal citations, like "in document X it says Y". Try to avoid giving false or misleading information. Feel free to say you don't know.
Try to be helpful, polite, honest, sophisticated, emotionally aware, and humble-but-knowledgeable.
That said, be practical and really do your best, and don't let caution get too much in the way of being useful.
To help answer the question, here's a few passages of high quality documents:\n{all_texts}
Now please respond to my question: {user_question}"""

    # "Please answer the following question. It's good to quote 'your documents' directly, something like 'from ABS source it says XYZ' Feel free to say you don't know. \nHere's a few passages of the high quality 'your documents':\n"

    return stuffed_prompt

  def get_stuffed_prompt(self, search_query: str, course_name: str, token_limit: int = 7_000) -> str:
    """
    Returns
      String: A fully formatted prompt string.
    """
    try:
      top_n = 90
      start_time_overall = time.monotonic()
      o = OpenAIEmbeddings(openai_api_type=OPENAI_API_TYPE)
      user_query_embedding = o.embed_documents(search_query)[0]  # type: ignore
      myfilter = models.Filter(must=[
          models.FieldCondition(key='course_name', match=models.MatchValue(value=course_name)),
      ])

      found_docs = self.qdrant_client.search(
          collection_name=os.environ['QDRANT_COLLECTION_NAME'],
          query_filter=myfilter,
          with_vectors=False,
          query_vector=user_query_embedding,
          limit=top_n  # Return 5 closest points
      )
      print("Search results: ", found_docs)
      if len(found_docs) == 0:
        return search_query

      pre_prompt = "Please answer the following question. Use the context below, called your documents, only if it's helpful and don't use parts that are very irrelevant. It's good to quote from your documents directly, when you do always use Markdown footnotes for citations. Use react-markdown superscript to number the sources at the end of sentences (1, 2, 3...) and use react-markdown Footnotes to list the full document names for each number. Use ReactMarkdown aka 'react-markdown' formatting for super script citations, use semi-formal style. Feel free to say you don't know. \nHere's a few passages of the high quality documents:\n"

      # count tokens at start and end, then also count each context.
      token_counter, _ = count_tokens_and_cost(pre_prompt + '\n\nNow please respond to my query: ' +
                                               search_query)  # type: ignore
      valid_docs = []
      for d in found_docs:
        if d.payload is not None:
          if "pagenumber" not in d.payload.keys():
            d.payload["pagenumber"] = d.payload["pagenumber_or_timestamp"]

          doc_string = f"---\nDocument: {d.payload['readable_filename']}{', page: ' + str(d.payload['pagenumber']) if d.payload['pagenumber'] else ''}\n{d.payload.get('page_content')}\n"
          num_tokens, prompt_cost = count_tokens_and_cost(doc_string)  # type: ignore

          # print(f"Page: {d.payload.get('page_content', ' '*100)[:100]}...")
          print(
              f"tokens used/limit: {token_counter}/{token_limit}, tokens in chunk: {num_tokens}, prompt cost of chunk: {prompt_cost}. 📄 File: {d.payload.get('readable_filename', '')}"
          )
          if token_counter + num_tokens <= token_limit:
            token_counter += num_tokens
            valid_docs.append(
                Document(page_content=d.payload.get('page_content', '<Missing page content>'), metadata=d.payload))
          else:
            continue

      # Convert the valid_docs to full prompt
      separator = '---\n'  # between each context
      context_text = separator.join(
          f"Document: {d.metadata['readable_filename']}{', page: ' + str(d.metadata['pagenumber']) if d.metadata['pagenumber'] else ''}\n{d.page_content}\n"
          for d in valid_docs)

      # Create the stuffedPrompt
      stuffedPrompt = (pre_prompt + context_text + '\n\nNow please respond to my query: ' + search_query)

      TOTAL_num_tokens, prompt_cost = count_tokens_and_cost(stuffedPrompt, openai_model_name='gpt-4')  # type: ignore
      print(f"Total tokens: {TOTAL_num_tokens}, prompt_cost: {prompt_cost}")
      print("total docs: ", len(found_docs))
      print("num docs used: ", len(valid_docs))

      print(f"⏰ ^^ Runtime of getTopContexts: {(time.monotonic() - start_time_overall):.2f} seconds")
      return stuffedPrompt
    except Exception as e:
      # return full traceback to front end
      err: str = f"Traceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:{e}"  # type: ignore
      print(err)
      sentry_sdk.capture_exception(e)
      return err

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
        found_doc.metadata['pagenumber'] = found_doc.metadata['pagenumber_or_timestamp']

    contexts = [
        {
            'text': doc.page_content,
            'readable_filename': doc.metadata['readable_filename'],
            'course_name ': doc.metadata['course_name'],
            's3_path': doc.metadata['s3_path'],
            'pagenumber': doc.metadata['pagenumber'],  # this because vector db schema is older...
            # OPTIONAL PARAMS...
            'url': doc.metadata.get('url'),  # wouldn't this error out?
            'base_url': doc.metadata.get('base_url'),
        } for doc in found_docs
    ]

    return contexts


if __name__ == '__main__':
  pass
