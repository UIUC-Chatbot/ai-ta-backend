import os
from pathlib import Path
# from re import L, T
from tempfile import TemporaryFile
from typing import Any, Dict, List, Literal, Union
from xml.dom.minidom import Document  # PDF to text

import boto3
import fitz
import supabase
from dotenv import load_dotenv
from flask import jsonify, request
from flask.json import jsonify
from langchain.document_loaders import S3DirectoryLoader
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
    # embeds = 
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

  def bulk_ingest(self, s3_paths: List[str] | str, course_name: str) -> Literal['Success']:
    
    if isinstance(s3_paths, str):
      s3_paths = [s3_paths]
    
    for s3_path in s3_paths:
      if s3_path.endswith('.pdf'):
        # todo check each return value for failures. If any fail, send emails.
        self.ingest_PDFs(s3_path, course_name)
      elif s3_path.endswith('.txt'):
        # self.ingest_text(s3_path, course_name)
        print('Not yet implemented')
      elif s3_path.endswith('.srt'):
        print('Not yet implemented')
      elif s3_path.endswith('.docx'):
        # https://python.langchain.com/en/latest/modules/indexes/document_loaders/examples/microsoft_word.html
        print('Not yet implemented')
      elif s3_path.endswith('.srt'):
        print('Not yet implemented')
      elif s3_path.endswith('.srt'):
        print('Not yet implemented')
    
    return "Success"
    
  def _ingest_single_PDF(self, pdf_tmpfile, s3_pdf_path: str) -> Literal['Success']:
    """
    Private method. Use ingest_PDFs() instead.
    
    Both OCR the PDF, and split the text into chunks. Returns chunks as List[Document].
      LangChain `Documents` have .metadata and .page_content attributes.
    Be sure to use TemporaryFile() to avoid memory leaks!
    """
    ### READ OCR of PDF
    pdf_pages_OCRed: List[Dict] = []
    for i, page in enumerate(fitz.open(pdf_tmpfile)):
      text = page.get_text().encode("utf8").decode('ascii', errors='ignore')  # get plain text (is in UTF-8)
      pdf_pages_OCRed.append(dict(text=text,
                          page_number=i,
                          textbook_name=Path(s3_pdf_path).name))
    print(len(pdf_pages_OCRed))
    metadatas = [dict(page_number=page['page_number'], textbook_name=page['textbook_name']) for page in pdf_pages_OCRed]
    pdf_texts = [page['text'] for page in pdf_pages_OCRed]
    assert len(metadatas) == len(pdf_texts), 'must have equal number of pages and metadata objects'

    #### SPLIT TEXTS
    # good examples here: https://langchain.readthedocs.io/en/latest/modules/utils/combine_docs_examples/textsplitter.html
    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
      chunk_size=1000,
      chunk_overlap=150,
      separators=". ", # try to split on sentences... 
    )
    texts: List[Document] = text_splitter.create_documents(texts=pdf_texts, metadatas=metadatas)

    def remove_small_contexts(texts: List[Document]) -> List[Document]:
      # Remove TextSplit contexts with fewer than 50 chars.
      return [doc for doc in texts if len(doc.page_content) > 50]
    
    texts = remove_small_contexts(texts=texts)
  
    # upload to Qdrant
    self.vectorstore.add_texts([doc.page_content for doc in docs], [doc.metadata for doc in docs])

    return "Success"

  def ingest_PDFs(self, s3_pdf_paths: str | List[str]) -> Literal['Error', 'Success']:
    """
    Main function. Ingests single PDF into Qdrant.
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
            self._ingest_single_PDF(pdf_tmpfile, s3_pdf_path)
          except Exception as e:
            print(e)
    except Exception as e:
      print(e)
      return "Error"
    return "Success"
  
  def ingest_S3_directory(self, s3_dir_path: str) -> Literal['Error', 'Success']:
    """
    BAD BECAUSE: can't have individual error messages per file (literally impossible)
    can't do fancier things per file. So limiting.
    
    Ingest whole dir. Seems like many failure cases... Good rough prototype....
    Docs: https://python.langchain.com/en/latest/modules/indexes/document_loaders/examples/aws_s3_directory.html
    """
    try:
      # assert s3_dir_path.endswith('/'), 's3_dir_path must end with /'
      loader = S3DirectoryLoader(os.environ['S3_BUCKET_NAME'], prefix=s3_dir_path)
      docs = loader.load()
      print("--"*20)
      print(docs[0].page_content)
      print("--"*20)
      print(f"Loaded {len(docs)} documents from S3")
      
      # self.vectorstore.add_texts([doc.page_content for doc in docs], [doc.metadata for doc in docs])
      qdrant = Qdrant.from_documents(
          docs, 
          OpenAIEmbeddings(), 
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
  def getTopContexts(self, search_query: str) -> List[Document]:
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
      language: str = request.args.get('course_name')
    except Exception as e:
      print(f"No course name provided. Error: \n{e}")
      
    found_docs = self.vectorstore.similarity_search(search_query)
    print("found_docs:")
    print(found_docs)
    
    # {'course_name': course_name, 'contexts': [{'source_name': 'Lumetta_notes', 'source_location': 'pg. 19', 'text': 'In FSM, we do this...'}, {'source_name': 'Lumetta_notes', 'source_location': 'pg. 20', 'text': 'In Assembly language, the code does that...'},]}
    return self.format_for_json(found_docs)
  
  def format_for_json(self, found_docs: List[Document]) -> List[Dict]:
    """Formatting only: e
      {'course_name': course_name, 'contexts': [{'source_name': 'Lumetta_notes', 'source_location': 'pg. 19', 'text': 'In FSM, we do this...'}, {'source_name': 'Lumetta_notes', 'source_location': 'pg. 20', 'text': 'In Assembly language, the code does that...'},]}

    Args:
        found_docs (List[Document]): _description_

    Raises:
        Exception: _description_

    Returns:
        List[Dict]: _description_
    """
    
    # TODO fix 
    contexts = [
      {'source_name': doc.metadata['source'], 
       'source_location': doc.metadata['source'], 
       'text': doc.page_content} 
      for doc in found_docs]
    
    return contexts
    
    


    language: str = request.args.get('course_name')
    response:str = jsonify({"language": f"You said: {language}"})
    response.headers.add('Access-Control-Allow-Origin', '*')
    if language == 'error':
      raise Exception('This is an error message!')
    return response