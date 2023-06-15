import asyncio
import datetime
import inspect
import math
import os
import subprocess
# from xml.dom.minidom import Document  # PDF to text
# from re import L, T
import traceback
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryFile
from typing import Any, Dict, List, Literal, Union

import boto3
import fitz
import supabase
from arize.api import Client
from arize.pandas.embeddings import EmbeddingGenerator, UseCases
# from arize.utils import ModelTypes
# from arize.utils.ModelTypes import GENERATIVE_LLM
from arize.utils.types import (Embedding, EmbeddingColumnNames, Environments, Metrics, ModelTypes, Schema)
from dotenv import load_dotenv
from flask import jsonify, request
from langchain.document_loaders import (Docx2txtLoader, S3DirectoryLoader, SRTLoader)
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Qdrant
from langchain import PromptTemplate, OpenAI, LLMChain
from langchain.chains.summarize import load_summarize_chain
from qdrant_client import QdrantClient, models

# from regex import F
# from sqlalchemy import JSON

# load API keys from globally-availabe .env file
load_dotenv(dotenv_path='../.env', override=True)


class Ingest():
  """
  Contains all methods for building and using vector databases.
  """

  def __init__(self):
    """
    Initialize AWS S3, Qdrant, and Supabase.
    """

    # vector DB
    self.qdrant_client = QdrantClient(
        url=os.getenv('QDRANT_URL'),
        api_key=os.getenv('QDRANT_API_KEY'),
    )
    self.vectorstore = Qdrant(
        client=self.qdrant_client,
        collection_name=os.getenv('QDRANT_COLLECTION_NAME'),  # type: ignore
        embeddings=OpenAIEmbeddings())  # type: ignore

    # S3
    self.s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        # aws_session_token=,  # Comment this line if not using temporary credentials
    )

    # Create a Supabase client
    self.supabase_client = supabase.create_client(
        supabase_url=os.getenv('SUPABASE_URL'),  # type: ignore
        supabase_key=os.getenv('SUPABASE_API_KEY'))  # type: ignore

    self.arize_client = Client(space_key=os.getenv('ARIZE_SPACE_KEY'), api_key=os.getenv('ARIZE_API_KEY'))  # type: ignore

    return None

  def get_context_stuffed_prompt(self, user_question: str, course_name: str, top_n: int, top_k_to_search: int) -> str:
    """
    Get a stuffed prompt for a given user question and course name.
    Args : 
      user_question (str)
      course_name (str) : used for metadata filtering
    Returns : str
      a very long "stuffed prompt" with question + summaries of 20 most relevant documents.
     """
    #MMR with metadata filtering based on course_name
    print(f"user question {user_question}")
    print(f"course_name {course_name}")
    print(f"top_n {top_n}")
    print(f"top_k_to_search {top_k_to_search}")

    found_docs = self.vectorstore.max_marginal_relevance_search(user_question, k=top_n, fetch_k=top_k_to_search)
    print("MMR done")
    prompt_template = """Provide a comprehensive summary of the given text, based on the question.
    {text}
    Question : {question}
    The summary should cover all the key points only relevant to the question, while also condensing the information into a concise and easy-to-understand format. 
    Please ensure that the summary includes relevant details and examples that support the main ideas, while avoiding any unnecessary information or repetition. 
    Feel free to include references, sentence fragments, keywords or anything that could help someone learn about it, only as it relates to the given question. 
    The length of the summary should be as short as possible, without losing relevant information.
    """
    PROMPT = PromptTemplate(template=prompt_template, input_variables=["text", "question"])
    chain = load_summarize_chain(OpenAI(temperature=0, batch_size=20, openai_api_key=os.getenv('OPENAI_API_KEY')),
                                 chain_type="map_reduce",
                                 return_intermediate_steps=True,
                                 map_prompt=PROMPT,
                                 combine_prompt=PROMPT,
                                 verbose=False)
    results = chain({"input_documents": found_docs, "question": user_question}, return_only_outputs=True)  #get results

    #to return long stuffed prompt
    separator = '---'  # between each context
    all_texts = ''
    for doc, summary in zip(found_docs, results["intermediate_steps"]):
      doc_text = f"Document: {doc.metadata['readable_filename']}, page number (if exists): {doc.metadata['pagenumber_or_timestamp']}\n"
      summary_text = f"Summary: {summary}\n"
      all_texts += doc_text + summary_text + separator + '\n'

    stuffed_prompt = """Please answer the following question. 
    Use the context below, called 'official course materials,' only if it's helpful and don't use parts that are very irrelevant. 
    It's good to quote the official course materials directly, something like 'from ABS source it says XYZ'. Feel free to say you don't know. 
    \nHere's a few passages of high quality official course materials:\n %s 
    \n\nNow please respond to my query: %s """ % (all_texts, user_question)

    return stuffed_prompt

  def log_to_arize(self, course_name: str, user_question: str, llm_completion: str) -> str:
    import pandas as pd

    features = {
        'state': 'wa',
        'city': 'seattle',
        'merchant_name': 'Starbucks Coffee',
        'pos_approved': True,
        'item_count': 2,
        'merchant_type': 'coffee shop',
        'charge_amount': 22.11,
    }

    #example tags
    tags = {
        'age': 21,
        'zip_code': '94610',
        'device_os': 'MacOS',
        'server_node_id': 120,
    }

    #example embeddings
    embedding_features = {
        # 'image_embedding': Embedding(
        #     vector=np.array([1.0, 2, 3]), # type: ignore
        #     link_to_data='https://my-bucket.s3.us-west-2.amazonaws.com/puppy.png',
        # ),
        'prompt':
            Embedding(
                vector=pd.Series([6.0, 1.0, 2.0, 6.0]),  # type: ignore
                data='slightly different This is a test sentence',
            ),
        'completion':
            Embedding(
                vector=pd.Series([15.0, 10.0, 1.0, 9.0]),  # type: ignore
                data=['slightly', 'different', 'This', 'is', 'a', 'sample', 'token', 'array'],
            ),
    }

    #log the prediction
    response = self.arize_client.log(
        prediction_id=str(uuid.uuid4()),
        prediction_label=llm_completion,
        model_id='kas-model-1',
        # model_type=ModelTypes.GENERATIVE_LLM, # I think this is a bug.
        model_type=ModelTypes.SCORE_CATEGORICAL,
        environment=Environments.PRODUCTION,
        model_version='v1',
        prediction_timestamp=int(datetime.datetime.now().timestamp()),
        features=features,
        embedding_features=embedding_features,
        tags=tags,
    )

    ## Listen to response code to ensure successful delivery
    res = response.result()
    if res.status_code == 200:
      print('Success sending Prediction!')
      return "Success logging to Arize!"
    else:
      print(f'Log failed with response code {res.status_code}, {res.text}')
      return f'Log failed with response code {res.status_code}, {res.text}'

  def bulk_ingest(self, s3_paths: Union[List[str], str], course_name: str) -> Dict[str, List[str]]:
    # https://python.langchain.com/en/latest/modules/indexes/document_loaders/examples/microsoft_word.html
    success_status = {"success_ingest": [], "failure_ingest": []}

    try:
      if isinstance(s3_paths, str):
        s3_paths = [s3_paths]

      for s3_path in s3_paths:
        # print("s3_path", s3_path)
        # todo check each return value for failures. If any fail, send emails.

        if s3_path.endswith('.pdf'):
          ret = self._ingest_single_pdf(s3_path, course_name)
          if ret != "Success":
            success_status['failure_ingest'].append(s3_path)
          else:
            success_status['success_ingest'].append(s3_path)
        elif s3_path.endswith('.txt'):
          ret = self._ingest_single_txt(s3_path, course_name)
          #print('Not yet implemented')
          #ret = "failure"
          if ret != "Success":
            success_status['failure_ingest'].append(s3_path)
          else:
            success_status['success_ingest'].append("TXT -- Not yet implemented: " + s3_path)
        elif s3_path.endswith('.srt'):
          ret = self._ingest_single_srt(s3_path, course_name)
          if ret != "Success":
            success_status['failure_ingest'].append(s3_path)
          else:
            success_status['success_ingest'].append(s3_path)
        elif s3_path.endswith('.docx'):
          ret = self._ingest_single_docx(s3_path, course_name)
          if ret != "Success":
            success_status['failure_ingest'].append(s3_path)
          else:
            success_status['success_ingest'].append(s3_path)
        elif s3_path.endswith('.ppt') or s3_path.endswith('.pptx'):
          ret = self._ingest_single_ppt(s3_path, course_name)
          if ret != "Success":
            success_status['failure_ingest'].append(s3_path)
          else:
            success_status['success_ingest'].append(s3_path)

      return success_status
    except Exception as e:
      success_status['failure_ingest'].append("MAJOR ERROR IN /bulk_ingest: Error: " + str(e))
      return success_status

  def _ingest_single_docx(self, s3_path: str, course_name: str) -> str:
    try:
      with NamedTemporaryFile() as tmpfile:
        # download from S3 into pdf_tmpfile
        print("Bucket: ", os.getenv('S3_BUCKET_NAME'))
        print("Key: ", s3_path)
        self.s3_client.download_fileobj(Bucket=os.getenv('S3_BUCKET_NAME'), Key=s3_path, Fileobj=tmpfile)
        print("GOT THE FILE")
        print(tmpfile.name)

        loader = Docx2txtLoader(tmpfile.name)
        documents = loader.load()

        texts = [doc.page_content for doc in documents]
        metadatas: List[Dict[str, Any]] = [{
            'course_name': course_name,
            's3_path': s3_path,
            'readable_filename': Path(s3_path).stem,
            'pagenumber_or_timestamp': '',
        } for doc in documents]

        self.split_and_upload(texts=texts, metadatas=metadatas)
        return "Success"
    except Exception as e:
      print(f"ERROR IN DOCX {e}")
      return f"Error: {e}"

  def _ingest_single_srt(self, s3_path: str, course_name: str) -> str:
    try:
      with NamedTemporaryFile() as tmpfile:
        # download from S3 into pdf_tmpfile
        self.s3_client.download_fileobj(Bucket=os.getenv('S3_BUCKET_NAME'), Key=s3_path, Fileobj=tmpfile)

        loader = SRTLoader(tmpfile.name)
        documents = loader.load()

        texts = [doc.page_content for doc in documents]
        metadatas: List[Dict[str, Any]] = [{
            'course_name': course_name,
            's3_path': s3_path,
            'readable_filename': Path(s3_path).stem,
            'pagenumber_or_timestamp': '',
        } for doc in documents]

        self.split_and_upload(texts=texts, metadatas=metadatas)
        return "Success"
    except Exception as e:
      print(f"SRT ERROR {e}")
      return f"Error: {e}"

  def _ingest_single_pdf(self, s3_path: str, course_name: str):
    """
    Both OCR the PDF. And grab the first image as a PNG. 
      LangChain `Documents` have .metadata and .page_content attributes.
    Be sure to use TemporaryFile() to avoid memory leaks!
    """
    # first_page_png = pix.tobytes(output='png', jpg_quality=95)
    print("IN INGEST PDF")
    try:
      with NamedTemporaryFile() as pdf_tmpfile:
        # download from S3 into pdf_tmpfile
        self.s3_client.download_fileobj(Bucket=os.getenv('S3_BUCKET_NAME'), Key=s3_path, Fileobj=pdf_tmpfile)

        ### READ OCR of PDF
        print("Right before opening pdf")
        doc = fitz.open(pdf_tmpfile.name)  # type: ignore

        # improve quality of the image
        zoom_x = 2.0  # horizontal zoom
        zoom_y = 2.0  # vertical zoom
        mat = fitz.Matrix(zoom_x, zoom_y)  # zoom factor 2 in each dimension

        pdf_pages_OCRed: List[Dict] = []
        for i, page in enumerate(doc):  # type: ignore

          # UPLOAD FIRST PAGE IMAGE to S3
          if i == 0:
            with NamedTemporaryFile(suffix=".png") as first_page_png:
              pix = page.get_pixmap(matrix=mat)
              pix.save(first_page_png)  # store image as a PNG

              s3_upload_path = str(Path(s3_path)).rsplit('.pdf')[0] + "-pg1-thumb.png"
              first_page_png.seek(0)  # Seek the file pointer back to the beginning
              with open(first_page_png.name, 'rb') as f:
                print("Uploading image png to S3")
                self.s3_client.upload_fileobj(f, os.getenv('S3_BUCKET_NAME'), s3_upload_path)

          # Extract text
          text = page.get_text().encode("utf8").decode('ascii', errors='ignore')  # get plain text (is in UTF-8)
          pdf_pages_OCRed.append(dict(text=text, page_number=i, readable_filename=Path(s3_path).stem))

        metadatas: List[Dict[str, Any]] = [
            {
                'course_name': course_name,
                's3_path': s3_path,
                'pagenumber_or_timestamp': page['page_number'] + 1,  # +1 for human indexing
                'readable_filename': page['readable_filename'],
            } for page in pdf_pages_OCRed
        ]
        pdf_texts = [page['text'] for page in pdf_pages_OCRed]

        self.split_and_upload(texts=pdf_texts, metadatas=metadatas)
    except Exception as e:
      print("ERROR IN PDF READING ")
      print(e)
      return f"Error {e}"
    return "Success"

  def _ingest_single_txt(self, s3_path: str, course_name: str) -> str:
    # ----- asmita's code -----
    try:
      with NamedTemporaryFile() as tmpfile:
        # download from S3 into pdf_tmpfile
        print("Bucket: ", os.environ['S3_BUCKET_NAME'])
        print("Key: ", s3_path)
        self.s3_client.download_fileobj(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_path, Fileobj=tmpfile)
        print("GOT THE FILE")
        print(tmpfile.name)

        loader = UnstructuredFileLoader(tmpfile.name)
        documents = loader.load()

        texts = [doc.page_content for doc in documents]
        metadatas: List[Dict[str, Any]] = [{
            'course_name': course_name,
            's3_path': s3_path,
            'readable_filename': Path(s3_path).stem,
            'pagenumber_or_timestamp': '',
        } for doc in documents]

        self.split_and_upload(texts=texts, metadatas=metadatas)
        return "Success"
    except Exception as e:
      print(f"ERROR IN TXT {e}")
      return f"Error: {e}"

  def _ingest_single_ppt(self, s3_path: str, course_name: str) -> str:
    # ----- asmita's code -----
    try:
      with NamedTemporaryFile() as tmpfile:
        # download from S3 into pdf_tmpfile
        print("Bucket: ", os.environ['S3_BUCKET_NAME'])
        print("Key: ", s3_path)
        self.s3_client.download_fileobj(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_path, Fileobj=tmpfile)
        print("GOT THE FILE")
        print(tmpfile.name)

        loader = UnstructuredPowerPointLoader(tmpfile.name)
        documents = loader.load()

        texts = [doc.page_content for doc in documents]
        metadatas: List[Dict[str, Any]] = [{
            'course_name': course_name,
            's3_path': s3_path,
            'readable_filename': Path(s3_path).stem,
            'pagenumber_or_timestamp': '',
        } for doc in documents]

        self.split_and_upload(texts=texts, metadatas=metadatas)
        return "Success"
    except Exception as e:
      print("ERROR IN PDF READING ")
      print(e)
      return f"Error {e}"
    return "Success"

  def ingest_coursera_url(self, url: str, course_name: str):
    """
    1. Download the coursera url to a temp file
    2. For each file downloaded, run it through the ingest_bulk method
    """

    print("starting ingest_coursera_url")

    certificate = "-ca 'FVhVoDp5cb-ZaoRr5nNJLYbyjCLz8cGvaXzizqNlQEBsG5wSq7AHScZGAGfC1nI0ehXFvWy1NG8dyuIBF7DLMA.X3cXsDvHcOmSdo3Fyvg27Q.qyGfoo0GOHosTVoSMFy-gc24B-_BIxJtqblTzN5xQWT3hSntTR1DMPgPQKQmfZh_40UaV8oZKKiF15HtZBaLHWLbpEpAgTg3KiTiU1WSdUWueo92tnhz-lcLeLmCQE2y3XpijaN6G4mmgznLGVsVLXb-P3Cibzz0aVeT_lWIJNrCsXrTFh2HzFEhC4FxfTVqS6cRsKVskPpSu8D9EuCQUwJoOJHP_GvcME9-RISBhi46p-Z1IQZAC4qHPDhthIJG4bJqpq8-ZClRL3DFGqOfaiu5y415LJcH--PRRKTBnP7fNWPKhcEK2xoYQLr9RxBVL3pzVPEFyTYtGg6hFIdJcjKOU11AXAnQ-Kw-Gb_wXiHmu63veM6T8N2dEkdqygMre_xMDT5NVaP3xrPbA4eAQjl9yov4tyX4AQWMaCS5OCbGTpMTq2Y4L0Mbz93MHrblM2JL_cBYa59bq7DFK1IgzmOjFhNG266mQlC9juNcEhc'"
    coursera_course_name = "operations-management-organization-and-analysis"
    always_use_flags = "-u kastanvday@gmail.com -p hSBsLaF5YM469# --ignore-formats mp4 --subtitle-language en"

    results = subprocess.run(f"coursera-dl {always_use_flags} {certificate} {coursera_course_name}",
                             check=True,
                             shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)  # capture_output=True,

    # use walkdir to find all files in the directory, send them to bulk ingest one by one.

    print(results)
    print("Done .. ")

  def split_and_upload(self, texts: List[str], metadatas: List[Dict[str, Any]]):
    """ This is usually the last step of document ingest. Chunk & upload to Qdrant (and Supabase.. todo).
    Takes in Text and Metadata (from Langchain doc loaders) and splits / uploads to Qdrant.
    
    good examples here: https://langchain.readthedocs.io/en/latest/modules/utils/combine_docs_examples/textsplitter.html

    Args:
        texts (List[str]): _description_
        metadatas (List[Dict[str, Any]]): _description_
    """
    assert len(texts) == len(metadatas), 'must have equal number of text strings and metadata dicts'

    try:
      text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
          chunk_size=1000,
          chunk_overlap=150,
          separators=". ",  # try to split on sentences... 
      )
      documents: List[Document] = text_splitter.create_documents(texts=texts, metadatas=metadatas)

      def remove_small_contexts(documents: List[Document]) -> List[Document]:
        # Remove TextSplit contexts with fewer than 50 chars.
        return [doc for doc in documents if len(doc.page_content) > 50]

      documents = remove_small_contexts(documents=documents)

      # upload to Qdrant
      self.vectorstore.add_texts([doc.page_content for doc in documents], [doc.metadata for doc in documents])
      data = [{"content": doc.page_content, "metadata": doc.metadata} for doc in documents]
      count = self.supabase_client.table(os.getenv('SUPABASE_TABLE')).insert(data).execute()  # type: ignore

      return "Success"
    except Exception as e:
      print(f'ERROR IN SPLIT AND UPLOAD {e}')
      return f"Error: {e}"

  def getAll(
      self,
      course_name: str,
  ):
    """Get all course materials based on course name.
    Args : 
        course_name (as uploaded on supabase)
    Returns : 
        list of dictionaries with distinct s3 path, readable_filename and course_name.
    """
    response = self.supabase_client.table(
        os.getenv('SUPABASE_TABLE')).select('metadata->>course_name, metadata->>s3_path, metadata->>readable_filename').eq(  # type: ignore
            'metadata->>course_name', course_name).execute()

    data = response.data
    unique_combinations = set()
    distinct_dicts = []

    for item in data:
      combination = (item['s3_path'], item['readable_filename'], item['course_name'])
      if combination not in unique_combinations:
        unique_combinations.add(combination)
        distinct_dicts.append(item)

    return distinct_dicts

  def getTopContexts(self, search_query: str, course_name: str, top_n: int = 4) -> Union[List[Dict], str]:
    """Here's a summary of the work.

    /GET arguments
      course name (optional) str: A json response with TBD fields.
      
    Returns
      JSON: A json response with TBD fields. See main.py:getTopContexts docs.
      or 
      String: An error message with traceback.
    """
    try:
      import time
      print("START get contexts")
      start_time_overall = time.monotonic()
      found_docs = self.vectorstore.similarity_search(search_query, k=top_n, filter={'course_name': course_name})

      # log to Supabase
      # todo: make this async. It's .6 seconds to log to Supabase. 1 second to get contexts.
      start_time = time.monotonic()
      context_arr = [{"content": doc.page_content, "metadata": doc.metadata} for doc in found_docs]
      one_user_question = {"prompt": search_query, "context": context_arr, "course_name": course_name}  # "completion": 'todo'
      self.supabase_client.table('llm-monitor').insert(one_user_question).execute()  # type: ignore
      print(f"⏰ Log to Supabase time: {(time.monotonic() - start_time):.2f} seconds")
      print("DONE Returning contexts")
      print(f"⏰ Overall runtime of contexts + logging to Supabase: {(time.monotonic() - start_time_overall):.2f} seconds")
      return self.format_for_json(found_docs)
    except Exception as e:
      # return full traceback to front end
      err: str = f"Traceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:{e}"  # type: ignore
      print(err)
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

    contexts = [{
        'text': doc.page_content,
        'readable_filename': doc.metadata['readable_filename'],
        'course_name ': doc.metadata['course_name'],
        's3_path': doc.metadata['s3_path'],
        'pagenumber_or_timestamp': doc.metadata['pagenumber_or_timestamp'],
    } for doc in found_docs]

    return contexts
