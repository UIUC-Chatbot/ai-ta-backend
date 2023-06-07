import inspect
import math
import os
# from xml.dom.minidom import Document  # PDF to text
# from re import L, T
import traceback
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryFile
from typing import Any, Dict, List, Literal, Union

import boto3
import fitz
import supabase
from dotenv import load_dotenv
from flask import jsonify, request
from langchain.document_loaders import (Docx2txtLoader, S3DirectoryLoader, SRTLoader)
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Qdrant
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
        url=os.environ['QDRANT_URL'],
        api_key=os.environ['QDRANT_API_KEY'],
    )
    self.vectorstore = Qdrant(client=self.qdrant_client,
                              collection_name=os.environ['QDRANT_COLLECTION_NAME'],
                              embeddings=OpenAIEmbeddings())  # type: ignore

    # S3
    self.s3_client = boto3.client(
        's3',
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        # aws_session_token=,  # Comment this line if not using temporary credentials
    )

    # Create a Supabase client
    self.supabase_client = supabase.create_client(supabase_url=os.environ.get('SUPABASE_URL'),
                                                  supabase_key=os.environ.get('SUPABASE_API_KEY'))

    return None

  def get_context_stuffed_prompt(self, user_question: str, course_name: str) -> str:
    """
    Get a stuffed prompt for a given user question and course name.
    
    TODO: implement this.
    
    Find top 100 documents (ideally using marginal_relevancy Langchain function)
    For each document, get GPT3.5-turbo to summarize. Use this prompt:
    Use the following portion of a long document to see if any of the text is relevant to answer the question. 
    ```
    Return any relevant text verbatim.
    {context}
    Question: {question}
    Relevant text, if any:
    ```

    Use LangChain map_reduce_QA to implement this in parallel.
    Write a function that takes in a question, and returns a very long "stuffed" prompt for GPT-4 to answer on the front-end. (You only construct the prompt for GPT-4, you don't actually return the answer).
    
    References:
    Example & Docs: https://python.langchain.com/en/latest/modules/chains/index_examples/question_answering.html#the-map-reduce-chain
    Code: https://github.com/hwchase17/langchain/blob/4092fd21dcabd1de273ad902fae2186ae5347e03/langchain/chains/question_answering/map_reduce_prompt.py#L11 
    """

    return f"TODO: Implement me! You asked for: {course_name}"

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
          # self.ingest_text(s3_path, course_name)
          print('Not yet implemented')
          ret = "failure"
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

      return success_status
    except Exception as e:
      success_status['failure_ingest'].append("MAJOR ERROR IN /bulk_ingest: Error: " + str(e))
      return success_status

  def _ingest_single_docx(self, s3_path: str, course_name: str) -> str:
    try:
      with NamedTemporaryFile() as tmpfile:
        # download from S3 into pdf_tmpfile
        print("Bucket: ", os.environ['S3_BUCKET_NAME'])
        print("Key: ", s3_path)
        self.s3_client.download_fileobj(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_path, Fileobj=tmpfile)
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
        self.s3_client.download_fileobj(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_path, Fileobj=tmpfile)

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
        self.s3_client.download_fileobj(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_path, Fileobj=pdf_tmpfile)

        ### READ OCR of PDF
        print("Right before opening pdf")
        doc = fitz.open(pdf_tmpfile.name)

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
                self.s3_client.upload_fileobj(f, os.environ['S3_BUCKET_NAME'], s3_upload_path)

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
      count = self.supabase_client.table(os.environ.get('SUPABASE_TABLE')).insert(data).execute()

      return "Success"
    except Exception as e:
      print(f'ERROR IN SPLIT AND UPLOAD {e}')
      return f"Error: {e}"

  def getAll(
      self,
      course_name: str,
  ):
    """Get all course materials based on course name.
    args : 
        course_name (as uploaded on supabase)
    Returns : 
        list of dictionaries with distinct s3 path, readable_filename and course_name.
    
    """
    response = self.supabase_client.table(
        os.environ.get('SUPABASE_TABLE')).select('metadata->>course_name, metadata->>s3_path, metadata->>readable_filename').eq(
            'metadata->>course_name', course_name).execute()

    data = response.data  #response is APIResponse object, we only pick the data
    unique_combinations = set()  #set to remove duplicates
    distinct_dicts = []  #list of dictionaries

    for item in data:
      combination = (item['s3_path'], item['readable_filename'], item['course_name'])  #unique combinations of all 3
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
      found_docs = self.vectorstore.similarity_search(search_query, k=top_n, filter={'course_name': course_name})
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
