import inspect
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
from langchain.document_loaders import (Docx2txtLoader, S3DirectoryLoader,
                                        SRTLoader)
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Qdrant
from qdrant_client import QdrantClient

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
                              embeddings=OpenAIEmbeddings())

    # S3
    self.s3_client = boto3.client(
        's3',
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        # aws_session_token=,  # Comment this line if not using temporary credentials
    )

    # Create a Supabase client
    # self.supabase_client = supabase.create_client(supabase_url=os.environ.get('SUPABASE_URL'), supabase_key=os.environ.get('SUPABASE_API_KEY'))

    return None

  def bulk_ingest(self, s3_paths: Union[List[str], str], course_name: str) -> str:
    # https://python.langchain.com/en/latest/modules/indexes/document_loaders/examples/microsoft_word.html
    try:
      if isinstance(s3_paths, str):
        s3_paths = [s3_paths]

      for s3_path in s3_paths:
        # print("s3_path", s3_path)
        # todo check each return value for failures. If any fail, send emails.

        if s3_path.endswith('.pdf'):
          self.ingest_PDFs(s3_path, course_name)
        elif s3_path.endswith('.txt'):
          # self.ingest_text(s3_path, course_name)
          print('Not yet implemented')
        elif s3_path.endswith('.srt'):
          print('SRT')
          ret = self._ingest_single_srt(s3_path, course_name)
          if ret != "Success":
            print(f"TODO: Send email about failure of this file: {s3_path}")
        elif s3_path.endswith('.docx'):
          print('DOCX')
          ret = self._ingest_single_docx(s3_path, course_name)
          if ret != "Success":
            print(f"TODO: Send email about failure of this file: {s3_path}")
      return "(TODO) Success or failure unknown"
    except Exception as e:
      return f"Error: {e}"

  def _ingest_single_docx(self, s3_path: str, course_name: str) -> str:
    try:
      with NamedTemporaryFile() as tmpfile:
        # download from S3 into pdf_tmpfile
        self.s3_client.download_fileobj(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_path, Fileobj=tmpfile)

        loader = Docx2txtLoader(tmpfile.name)
        documents = loader.load()

        metadatas = [
            dict(pagenumber_or_timestamp="", course_name=course_name, filename=Path(s3_path).stem, s3_path=s3_path) for doc in documents
        ]
        texts = [doc.page_content for doc in documents]

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

        metadatas = [
            dict(pagenumber_or_timestamp="", course_name=course_name, filename=Path(s3_path).stem, s3_path=s3_path) for doc in documents
        ]
        texts = [doc.page_content for doc in documents]

        self.split_and_upload(texts=texts, metadatas=metadatas)
        return "Success"
    except Exception as e:
      print(f"SRT ERROR {e}")
      return f"Error: {e}"

  def _ingest_single_pdf(self, pdf_tmpfile, s3_pdf_path: str, course_name: str):
    """
    Private method. Use ingest_PDFs() instead.
    
    Both OCR the PDF, and split the text into chunks. Returns chunks as List[Document].
      LangChain `Documents` have .metadata and .page_content attributes.
    Be sure to use TemporaryFile() to avoid memory leaks!
    """
    try:
      with TemporaryFile() as pdf_tmpfile:
        # download from S3 into pdf_tmpfile
        self.s3_client.download_fileobj(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_pdf_path, Fileobj=pdf_tmpfile)
    
        ### READ OCR of PDF
        pdf_pages_OCRed: List[Dict] = []
        for i, page in enumerate(fitz.open(pdf_tmpfile)): # type: ignore
          text = page.get_text().encode("utf8").decode('ascii', errors='ignore')  # get plain text (is in UTF-8)
          pdf_pages_OCRed.append(dict(text=text, page_number=i, filename=Path(s3_pdf_path).stem))
        print(len(pdf_pages_OCRed))
        metadatas = [
            dict(pagenumber_or_timestamp=page['page_number'], course_name=course_name, filename=page['filename'], s3_path=s3_pdf_path)
            for page in pdf_pages_OCRed
        ]
        pdf_texts = [page['text'] for page in pdf_pages_OCRed]

        self.split_and_upload(texts=pdf_texts, metadatas=metadatas)
    except Exception as e:
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
      return "Success"
    except Exception as e:
      print(f'ERROR IN SPLIT AND UPLOAD {e}')
      return f"Error: {e}"

  def ingest_PDFs(self, s3_pdf_paths: Union[str, List[str]], course_name: str) -> str:
    """Main function. Ingests single PDF into Qdrant.

    Args:
        s3_pdf_paths (Union[str, List[str]]): _description_
        course_name (str): _description_

    Returns:
        str: _description_
    """
    try:
      if isinstance(s3_pdf_paths, str):
        s3_pdf_paths = [s3_pdf_paths]

      for s3_pdf_path in s3_pdf_paths:
        with TemporaryFile() as pdf_tmpfile:
          # download from S3 into pdf_tmpfile
          self.s3_client.download_fileobj(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_pdf_path, Fileobj=pdf_tmpfile)
          try:
            # try to ingest single PDF
            self._ingest_single_pdf(pdf_tmpfile, s3_pdf_path, course_name)
          except Exception as e:
            print(e)
    except Exception as e:
      print(e)
      return f"Error {e}"
    return "Success"

  def DEPRICATED_ingest_S3_directory(self, s3_dir_path: str) -> Literal['Error', 'Success']:
    """
    BAD BECAUSE: can't have individual error messages per file (literally impossible)
    can't do fancier things per file. So limiting.
    
    Ingest whole dir. Seems like many failure cases... Good rough prototype....
    Docs: https://python.langchain.com/en/latest/modules/indexes/document_loaders/examples/aws_s3_directory.html
    """
    try:
      assert s3_dir_path.endswith('/'), 's3_dir_path must end with /'
      loader = S3DirectoryLoader(os.environ['S3_BUCKET_NAME'], prefix=s3_dir_path)
      docs = loader.load()
      print("--" * 20)
      print(docs[0].page_content)
      print("--" * 20)
      print(f"Loaded {len(docs)} documents from S3")

      self.vectorstore.add_texts([doc.page_content for doc in docs], [doc.metadata for doc in docs])
      qdrant = Qdrant.from_documents(
          docs,
          OpenAIEmbeddings(), # type: ignore
          url=os.environ['QDRANT_URL'],
          prefer_grpc=True,
          api_key=os.environ['QDRANT_API_KEY'],
          collection_name=os.environ['QDRANT_COLLECTION_NAME'],
      )
    except Exception as e:
      print(e)
      return "Error"
    return "Success"

  # todo
  def getTopContexts(self, search_query: str):
    """Here's a summary of the work.

    /GET arguments
      course name (optional) str: A json response with TBD fields.
      
    Returns
      JSON: A json response with TBD fields.

    Raises:
      Exception: Testing how exceptions are handled.
    ret = {'course_name': course_name, 'contexts': [{'source_name': 'Lumetta_notes', 'source_location': 'pg. 19', 'text': 'In FSM, we do this...'}, {'source_name': 'Lumetta_notes', 'source_location': 'pg. 20', 'text': 'In Assembly language, the code does that...'},]}
    """
    # todo: best way to handle optional arguments?
    try:
      found_docs = self.vectorstore.similarity_search(search_query)
      print("found_docs:")
      print(found_docs)

      # {'course_name': course_name, 'contexts': [{'source_name': 'Lumetta_notes', 'source_location': 'pg. 19', 'text': 'In FSM, we do this...'}, {'source_name': 'Lumetta_notes', 'source_location': 'pg. 20', 'text': 'In Assembly language, the code does that...'},]}
      return self.format_for_json(found_docs)
    except Exception as e:
      # return full traceback to front end.
      err: str = f"Traceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:{e}"
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
        'source_name': doc.metadata['source'],
        'source_location': doc.metadata['source'],
        'text': doc.page_content
    } for doc in found_docs]

    return contexts
