import asyncio
import inspect
import mimetypes
# import json
import os
import shutil
import subprocess
import time
import traceback
from pathlib import Path
from tempfile import NamedTemporaryFile  # TemporaryFile
from typing import Any, Dict, List, Optional, Tuple, Union  # Literal

import boto3
# import requests
import fitz
import openai
import requests
import supabase
from bs4 import BeautifulSoup
# from arize.api import Client
# from arize.pandas.embeddings import EmbeddingGenerator, UseCases
# from arize.utils import ModelTypes
# from arize.utils.ModelTypes import GENERATIVE_LLM
# # from arize.utils.types import (Embedding, EmbeddingColumnNames, Environments,
# #                                Metrics, ModelTypes, Schema)
from langchain.document_loaders import (Docx2txtLoader, PythonLoader,
                                        SRTLoader, UnstructuredFileLoader, 
                                        UnstructuredPowerPointLoader, TextLoader, GitLoader)
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Qdrant
from pydub import AudioSegment
from qdrant_client import QdrantClient, models

from git import Repo

from ai_ta_backend.aws import upload_data_files_to_s3
from ai_ta_backend.extreme_context_stuffing import OpenAIAPIProcessor
from ai_ta_backend.utils_tokenization import count_tokens_and_cost


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
        embeddings=OpenAIEmbeddings())  

    # S3
    self.s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    )

    # Create a Supabase client
    self.supabase_client = supabase.create_client( # type: ignore
        supabase_url=os.getenv('SUPABASE_URL'),  # type: ignore
        supabase_key=os.getenv('SUPABASE_API_KEY'))  # type: ignore
    return None

  def get_context_stuffed_prompt(self, user_question: str, course_name: str, top_n: int, top_k_to_search: int) -> str:
    """
    Get a stuffed prompt for a given user question and course name.
    Args : 
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
    for i, doc in enumerate(found_docs):
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

    oai = OpenAIAPIProcessor(input_prompts_list=requests,
                             request_url='https://api.openai.com/v1/chat/completions',
                             api_key=os.getenv("OPENAI_API_KEY"),
                             max_requests_per_minute=1500,
                             max_tokens_per_minute=90000,
                             token_encoding_name='cl100k_base',
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
        num_tokens, prompt_cost = count_tokens_and_cost(text)
        if token_counter + num_tokens > max_tokens:
          print(f"Total tokens yet in loop {i} is {num_tokens}")
          break  # Stop building the string if it exceeds the maximum number of tokens
        token_counter += num_tokens
        filename = str(results[i][-1].get('readable_filename', ''))  # type: ignore
        pagenumber_or_timestamp = str(results[i][-1].get('pagenumber_or_timestamp', ''))  # type: ignore
        pagenumber = f", page: {pagenumber_or_timestamp}" if pagenumber_or_timestamp else ''
        doc = f"Document : filename: {filename}" + pagenumber
        summary = f"\nSummary: {text}"
        all_texts += doc + summary + '\n' + separator + '\n'

    stuffed_prompt = f"""Please answer the following question.
Use the context below, called 'your documents', only if it's helpful and don't use parts that are very irrelevant.
It's good to quote 'your documents' directly using informal citations, like "in document X it says Y". Try to avoid giving false or misleading information. Feel free to say you don't know.
Try to be helpful, polite, honest, sophisticated, emotionally aware, and humble-but-knowledgeable.
That said, be practical and really do your best, and don't let caution get too much in the way of being useful.
To help answer the question, here's a few passages of high quality documents:\n{all_texts}
Now please respond to my question: {user_question}"""

# "Please answer the following question. It's good to quote 'your documents' directly, something like 'from ABS source it says XYZ' Feel free to say you don't know. \nHere's a few passages of the high quality 'your documents':\n"

    return stuffed_prompt
  
  # def ai_summary(self, text: List[str], metadata: List[Dict[str, Any]]) -> List[str]:
  #   """
  #   Given a textual input, return a summary of the text.
  #   """
  #   #print("in AI SUMMARY")
  #   requests = []
  #   for i in range(len(text)):
  #     dictionary = {
  #           "model": "gpt-3.5-turbo",
  #           "messages": [{
  #               "role":
  #                   "system",
  #               "content":
  #                   "You are a factual summarizer of partial documents. Stick to the facts (including partial info when necessary to avoid making up potentially incorrect details), and say I don't know when necessary."
  #           }, {
  #               "role":
  #                   "user",
  #               "content":
  #                   f"Provide a descriptive summary of the given text:\n{text[i]}\nThe summary should cover all the key points, while also condensing the information into a concise format. The length of the summary should not exceed 3 sentences.",
  #           }],
  #           "n": 1,
  #           "max_tokens": 600,
  #           "metadata": metadata[i]
  #       }
  #     requests.append(dictionary)

  #   oai = OpenAIAPIProcessor(input_prompts_list=requests,
  #                            request_url='https://api.openai.com/v1/chat/completions',
  #                            api_key=os.getenv("OPENAI_API_KEY"),
  #                            max_requests_per_minute=1500,
  #                            max_tokens_per_minute=90000,
  #                            token_encoding_name='cl100k_base',
  #                            max_attempts=5,
  #                            logging_level=20)

  #   asyncio.run(oai.process_api_requests_from_file())
  #   #results: list[str] = oai.results
  #   #print(f"Cleaned results: {oai.cleaned_results}")
  #   summary = oai.cleaned_results
  #   return summary


  def bulk_ingest(self, s3_paths: Union[List[str], str], course_name: str, **kwargs) -> Dict[str, List[str]]:
    # https://python.langchain.com/en/latest/modules/indexes/document_loaders/examples/microsoft_word.html
    success_status = {"success_ingest": [], "failure_ingest": []}

    try:
      if isinstance(s3_paths, str):
        s3_paths = [s3_paths]

      for s3_path in s3_paths:
        ext = Path(s3_path).suffix # check mimetype of file
        # TODO: no need to download, just guess_type against the s3_path...
        with NamedTemporaryFile(suffix=ext) as tmpfile:
          self.s3_client.download_fileobj(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_path, Fileobj=tmpfile)
          mime_type = mimetypes.guess_type(tmpfile.name)[0]
          category, subcategory = mime_type.split('/')
        
        if s3_path.endswith('.html'):
          ret = self._ingest_html(s3_path, course_name, kwargs=kwargs)
          if ret != "Success":
            success_status['failure_ingest'].append(s3_path)
          else:
            success_status['success_ingest'].append(s3_path)
        elif s3_path.endswith('.py'):
          ret = self._ingest_single_py(s3_path, course_name)
          if ret != "Success":
            success_status['failure_ingest'].append(s3_path)
          else:
            success_status['success_ingest'].append(s3_path)
        elif s3_path.endswith('.vtt'):
          ret = self._ingest_single_vtt(s3_path, course_name)
          if ret != "Success":
            success_status['failure_ingest'].append(s3_path)
          else:
            success_status['success_ingest'].append(s3_path)
        elif s3_path.endswith('.pdf'):
          ret = self._ingest_single_pdf(s3_path, course_name, kwargs=kwargs)
          if ret != "Success":
            success_status['failure_ingest'].append(s3_path)
          else:
            success_status['success_ingest'].append(s3_path)
        elif s3_path.endswith('.txt') or s3_path.endswith('.md'):
          ret = self._ingest_single_txt(s3_path, course_name)
          if ret != "Success":
            success_status['failure_ingest'].append(s3_path)
          else:
            success_status['success_ingest'].append(s3_path)
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
        elif category == 'video' or category == 'audio':
          ret = self._ingest_single_video(s3_path, course_name)
          if ret != "Success":
            success_status['failure_ingest'].append(s3_path)
          else:
            success_status['success_ingest'].append(s3_path)  
      return success_status
    except Exception as e:
      success_status['failure_ingest'].append("MAJOR ERROR IN /bulk_ingest: Error: " + str(e))
      return success_status
  
  def _ingest_single_py(self, s3_path: str, course_name: str):
    try:
      print("in ingest_py")
      
      file_name = s3_path.split("/")[-1]
      file_path = "media/" + file_name

      self.s3_client.download_file(os.getenv('S3_BUCKET_NAME'), s3_path, file_path)
      loader = PythonLoader(file_path)
      documents = loader.load()
      
      texts = [doc.page_content for doc in documents]

      metadatas: List[Dict[str, Any]] = [{
            'course_name': course_name,
            's3_path': s3_path,
            'readable_filename': Path(s3_path).name,
            'pagenumber_or_timestamp': '',
        } for doc in documents]
      #print(texts)
      os.remove(file_path)

      success_or_failure = self.split_and_upload(texts=texts, metadatas=metadatas)
      return success_or_failure
      
      # with NamedTemporaryFile() as tmpfile:
      #   # download from S3 into tmpfile
      #   self.s3_client.download_fileobj(Bucket=os.getenv('S3_BUCKET_NAME'), Key=s3_path, Fileobj=tmpfile)
        
      #   print("filename: ", file_name)
      #   loader = PythonLoader("media/" + file_name)
      #   print("file: ", tmpfile)

      #   documents = loader.load()
      #   texts = [doc.page_content for doc in documents]

      #   metadatas: List[Dict[str, Any]] = [{
      #       'course_name': course_name,
      #       's3_path': s3_path,
      #       'readable_filename': Path(s3_path).name,
      #       'pagenumber_or_timestamp': '',
      #   } for doc in documents]

      #   print(documents)

      #   success_or_failure = self.split_and_upload(texts=texts, metadatas=metadatas)
      #   return success_or_failure
    except Exception as e:
      print(f"ERROR IN py READING {e}")

  def _ingest_single_vtt(self, s3_path: str, course_name: str):
    """
    Ingest a single .vtt file from S3.
    """
    try:
      with NamedTemporaryFile() as tmpfile:
        # download from S3 into vtt_tmpfile
        self.s3_client.download_fileobj(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_path, Fileobj=tmpfile)
        loader = TextLoader(tmpfile.name)
        documents = loader.load()
        texts = [doc.page_content for doc in documents]

        metadatas: List[Dict[str, Any]] = [{
            'course_name': course_name,
            's3_path': s3_path,
            'readable_filename': Path(s3_path).name,
            'pagenumber_or_timestamp': '',
        } for doc in documents]

        success_or_failure = self.split_and_upload(texts=texts, metadatas=metadatas)
        return success_or_failure
    except Exception as e:
      print(f"ERROR IN VTT READING {e}")

  def _ingest_html(self, s3_path: str, course_name: str, **kwargs) -> str:
    try:
      response = self.s3_client.get_object(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_path)
      raw_html = response['Body'].read().decode('utf-8')
      
      soup = BeautifulSoup(raw_html, 'html.parser')
      title = s3_path.replace("courses/"+course_name, "")
      title = title.replace(".html", "")
      title = title.replace("_", " ")
      title = title.replace("/", " ")
      title = title.strip()

      if kwargs['kwargs'] == {}:
        url = ''
        base_url = ''
      else:
        if 'url' in kwargs['kwargs'].keys():
          url = kwargs['kwargs']['url']
        else:
          url = ''
        if 'base_url' in kwargs['kwargs'].keys():
          base_url = kwargs['kwargs']['base_url']
        else:
          base_url = ''
      title = str(object=time.localtime()[1])+ "/" + str(time.localtime()[2]) + "/" + str(time.localtime()[0])[2:] + ' ' + str(title)

      text = [soup.get_text()]
      metadata: List[Dict[str, Any]] = [{
          'course_name': course_name,
          's3_path': s3_path,
          'readable_filename': str(title), # adding str to avoid error: unhashable type 'slice'  
          'url': url,
          'base_url': base_url,
          'pagenumber_or_timestamp': ''
      }]

      success_or_failure = self.split_and_upload(text, metadata)
      print(f"_ingest_html: {success_or_failure}")
      return success_or_failure
    except Exception as e:
      err: str = f"ERROR IN _ingest_html: {e}\nTraceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:{e}"  # type: ignore
      print(err)
      return f"_ingest_html Error: {e}"

  def _ingest_single_video(self, s3_path: str, course_name: str) -> str:
    """
    Ingest a single video file from S3.
    """
    try:
      # check for file extension
      file_ext = Path(s3_path).suffix
      print(file_ext[1:])

      openai.api_key = os.getenv('OPENAI_API_KEY')
      transcript_list = []
      #print(os.getcwd())
      with NamedTemporaryFile(suffix=file_ext) as video_tmpfile:
        # download from S3 into an video tmpfile
        self.s3_client.download_fileobj(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_path, Fileobj=video_tmpfile)
        # extract audio from video tmpfile
        mp4_version = AudioSegment.from_file(video_tmpfile.name, file_ext[1:])
        #print("Video file: ", video_tmpfile.name)

      # save the extracted audio as a temporary webm file
      with NamedTemporaryFile(suffix=".webm", dir="media", delete=False) as webm_tmpfile:
        mp4_version.export(webm_tmpfile, format="webm")
        #print("WEBM file: ", webm_tmpfile.name)

      # check file size
      file_size = os.path.getsize(webm_tmpfile.name)
      # split the audio into 25MB chunks
      if file_size > 26214400:
        # load the webm file into audio object
        full_audio = AudioSegment.from_file(webm_tmpfile.name, "webm")
        file_count = file_size // 26214400 + 1
        split_segment = 35 * 60 * 1000
        start = 0
        count = 0

        while count < file_count:
          with NamedTemporaryFile(suffix=".webm", dir="media", delete=False) as split_tmp:
            #print("Splitting file: ", split_tmp.name)
            if count == file_count - 1:
              # last segment
              audio_chunk = full_audio[start:]
            else:
              audio_chunk = full_audio[start:split_segment]

            audio_chunk.export(split_tmp.name, format="webm")

            # transcribe the split file and store the text in dictionary
            with open(split_tmp.name, "rb") as f:
              transcript = openai.Audio.transcribe("whisper-1", f)
            transcript_list.append(transcript['text'])  # type: ignore
          start += split_segment
          split_segment += split_segment
          count += 1
          os.remove(split_tmp.name)
      else:
        # transcribe the full audio
        with open(webm_tmpfile.name, "rb") as f:
          transcript = openai.Audio.transcribe("whisper-1", f)
        transcript_list.append(transcript['text'])  # type: ignore

      os.remove(webm_tmpfile.name)

      text = [txt for txt in transcript_list]
      metadatas: List[Dict[str, Any]] = [{
          'course_name': course_name,
          's3_path': s3_path,
          'readable_filename': Path(s3_path).name,
          'pagenumber_or_timestamp': text.index(txt),
      } for txt in text]

      self.split_and_upload(texts=text, metadatas=metadatas)
      return "Success"
    except Exception as e:
      print("ERROR IN VIDEO READING ")
      print(e)
      return f"Error {e}"

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
            'readable_filename': Path(s3_path).name,
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
            'readable_filename': Path(s3_path).name,
            'pagenumber_or_timestamp': '',
        } for doc in documents]

        self.split_and_upload(texts=texts, metadatas=metadatas)
        return "Success"
    except Exception as e:
      print(f"SRT ERROR {e}")
      return f"Error: {e}"

  def _ingest_single_pdf(self, s3_path: str, course_name: str, **kwargs):
    """
    Both OCR the PDF. And grab the first image as a PNG. 
      LangChain `Documents` have .metadata and .page_content attributes.
    Be sure to use TemporaryFile() to avoid memory leaks!
    """
    try:
      with NamedTemporaryFile() as pdf_tmpfile:
        # download from S3 into pdf_tmpfile
        self.s3_client.download_fileobj(Bucket=os.getenv('S3_BUCKET_NAME'), Key=s3_path, Fileobj=pdf_tmpfile)
        ### READ OCR of PDF
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
          pdf_pages_OCRed.append(dict(text=text, page_number=i, readable_filename=Path(s3_path).name))

        if kwargs['kwargs'] == {}:
          url = ''
          base_url = ''
        else:
          if 'url' in kwargs['kwargs'].keys():
            url = kwargs['kwargs']['url']
          else:
            url = ''
          if 'base_url' in kwargs['kwargs'].keys():
            base_url = kwargs['kwargs']['base_url']
          else:
            base_url = ''
          page['readable_filename'] = str(object=time.localtime()[1])+ "/" + str(time.localtime()[2]) + "/" + str(time.localtime()[0])[2:] + ' ' + page['readable_filename']

        
        metadatas: List[Dict[str, Any]] = [
            {
                'course_name': course_name,
                's3_path': s3_path,
                'pagenumber_or_timestamp': page['page_number'] + 1,  # +1 for human indexing
                'readable_filename': page['readable_filename'],
                'url': url,
                'base_url': base_url,
            } for page in pdf_pages_OCRed
        ]
        pdf_texts = [page['text'] for page in pdf_pages_OCRed]

        self.split_and_upload(texts=pdf_texts, metadatas=metadatas)
        print("Success pdf ingest")
    except Exception as e:
      print("ERROR IN PDF READING ")
      print(e)
      return f"Error {e}"
    return "Success"

  def _ingest_single_txt(self, s3_path: str, course_name: str) -> str:
    """Ingest a single .txt or .md file from S3.
    Args:
        s3_path (str): A path to a .txt file in S3
        course_name (str): The name of the course
    Returns:
        str: "Success" or an error message
    """
    try:
      # NOTE: slightly different method for .txt files, no need for download. It's part of the 'body'
      response = self.s3_client.get_object(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_path)
      text = response['Body'].read().decode('utf-8')
      text = [text]
    
      metadatas: List[Dict[str, Any]] = [{
          'course_name': course_name,
          's3_path': s3_path,
          'readable_filename': Path(s3_path).name,
          'pagenumber_or_timestamp': '',
        }]

      success_or_failure = self.split_and_upload(texts=text, metadatas=metadatas)
      return success_or_failure
    except Exception as e:
      print(f"ERROR IN TXT READING {e}")
      return f"Error: {e}"
  
  def _ingest_single_ppt(self, s3_path: str, course_name: str) -> str:
    """
    Ingest a single .ppt or .pptx file from S3.
    """
    try:
      with NamedTemporaryFile() as tmpfile:
        # download from S3 into pdf_tmpfile
        #print("in ingest PPTX")
        self.s3_client.download_fileobj(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_path, Fileobj=tmpfile)

        loader = UnstructuredPowerPointLoader(tmpfile.name)
        documents = loader.load()

        texts = [doc.page_content for doc in documents]
        metadatas: List[Dict[str, Any]] = [{
            'course_name': course_name,
            's3_path': s3_path,
            'readable_filename': Path(s3_path).name,
            'pagenumber_or_timestamp': '', 
        } for doc in documents]

        self.split_and_upload(texts=texts, metadatas=metadatas)
        return "Success"
    except Exception as e:
      print("ERROR IN PDF READING ")
      print(e)
      return f"Error {e}"

  def list_files_recursively(self, bucket, prefix):
    all_files = []
    continuation_token = None

    while True:
      list_objects_kwargs = {
          'Bucket': bucket,
          'Prefix': prefix,
      }
      if continuation_token:
        list_objects_kwargs['ContinuationToken'] = continuation_token

      response = self.s3_client.list_objects_v2(**list_objects_kwargs)

      if 'Contents' in response:
        for obj in response['Contents']:
          all_files.append(obj['Key'])

      if response['IsTruncated']:
        continuation_token = response['NextContinuationToken']
      else:
        break

    return all_files
  
  def ingest_coursera(self, coursera_course_name: str, course_name: str) -> str:
    """ Download all the files from a coursera course and ingest them.
    
    1. Download the coursera content. 
    2. Upload to S3 (so users can view it)
    3. Run everything through the ingest_bulk method.

    Args:
        coursera_course_name (str): The name of the coursera course.
        course_name (str): The name of the course in our system.

    Returns:
        _type_: Success or error message.
    """
    certificate = "-ca 'FVhVoDp5cb-ZaoRr5nNJLYbyjCLz8cGvaXzizqNlQEBsG5wSq7AHScZGAGfC1nI0ehXFvWy1NG8dyuIBF7DLMA.X3cXsDvHcOmSdo3Fyvg27Q.qyGfoo0GOHosTVoSMFy-gc24B-_BIxJtqblTzN5xQWT3hSntTR1DMPgPQKQmfZh_40UaV8oZKKiF15HtZBaLHWLbpEpAgTg3KiTiU1WSdUWueo92tnhz-lcLeLmCQE2y3XpijaN6G4mmgznLGVsVLXb-P3Cibzz0aVeT_lWIJNrCsXrTFh2HzFEhC4FxfTVqS6cRsKVskPpSu8D9EuCQUwJoOJHP_GvcME9-RISBhi46p-Z1IQZAC4qHPDhthIJG4bJqpq8-ZClRL3DFGqOfaiu5y415LJcH--PRRKTBnP7fNWPKhcEK2xoYQLr9RxBVL3pzVPEFyTYtGg6hFIdJcjKOU11AXAnQ-Kw-Gb_wXiHmu63veM6T8N2dEkdqygMre_xMDT5NVaP3xrPbA4eAQjl9yov4tyX4AQWMaCS5OCbGTpMTq2Y4L0Mbz93MHrblM2JL_cBYa59bq7DFK1IgzmOjFhNG266mQlC9juNcEhc'"
    always_use_flags = "-u kastanvday@gmail.com -p hSBsLaF5YM469# --ignore-formats mp4 --subtitle-language en --path ./coursera-dl"

    try:
      results = subprocess.run(f"coursera-dl {always_use_flags} {certificate} {coursera_course_name}",
                               check=True,
                               shell=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)  # capture_output=True,
      dl_results_path = os.path.join('coursera-dl', coursera_course_name)
      s3_paths: Union[List, None] = upload_data_files_to_s3(course_name, dl_results_path)

      if s3_paths is None:
        return "Error: No files found in the coursera-dl directory"

      print("starting bulk ingest")
      start_time = time.monotonic()
      self.bulk_ingest(s3_paths, course_name)
      print("completed bulk ingest")
      print(f"⏰ Runtime: {(time.monotonic() - start_time):.2f} seconds")

      # Cleanup the coursera downloads
      shutil.rmtree(dl_results_path)

      return "Success"
    except Exception as e:
      err: str = f"Traceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:{e}"  # type: ignore
      print(err)
      return err
    
  def ingest_github(self, github_url: str, course_name: str) -> str:
    """
    Clones the given GitHub URL and uses Langchain to load data.
    1. Clone the repo
    2. Use Langchain to load the data
    3. Pass to split_and_upload()
    Args:
        github_url (str): The Github Repo URL to be ingested.
        course_name (str): The name of the course in our system.

    Returns:
        _type_: Success or error message.
    """
    print("in ingest_github")

    try:
      repo_path = "media/cloned_repo"
      repo = Repo.clone_from(github_url, to_path=repo_path, depth=1, clone_submodules=False)
      branch = repo.head.reference

      loader = GitLoader(repo_path="media/cloned_repo", branch=branch)
      data = loader.load()
      shutil.rmtree("media/cloned_repo")
      # create metadata for each file in data 
      texts = [doc.page_content for doc in data]
      metadatas: List[Dict[str, Any]] = [{
              'course_name': course_name,
              's3_path': '',
              'readable_filename': doc.metadata['file_name'],
              'url': github_url,
              'pagenumber_or_timestamp': '', 
          } for doc in data]
      self.split_and_upload(texts=texts, metadatas=metadatas)
      return "Success"
    except Exception as e:
      print(f"ERROR IN GITHUB INGEST {e}")
      return f"Error: {e}"

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
      # generate AI summary
      # summary = self.ai_summary(texts, metadatas)
      # for i in range(len(summary)):
      #   metadatas[i]['summary'] = summary[i]

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
      count = self.supabase_client.table(os.getenv('MATERIALS_SUPABASE_TABLE')).insert(data).execute()  # type: ignore

      return "Success"
    except Exception as e:
      err: str = f"ERROR IN split_and_upload(): Traceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:{e}"  # type: ignore
      print(err)
      return err
    
  def delete_entire_course(self, course_name: str):
    """Delete entire course.
    
    Delete materials from S3, Supabase SQL, Vercel KV, and QDrant vector DB

    Args:
        course_name (str): _description_
    """
    print(f"Deleting entire course: {course_name}")
    try:
      # Delete file from S3
      objects_to_delete = self.s3_client.list_objects(Bucket=os.getenv('S3_BUCKET_NAME'), Prefix=f'courses/{course_name}/')
      for object in objects_to_delete['Contents']:
        self.s3_client.delete_object(Bucket=os.getenv('S3_BUCKET_NAME'), Key=object['Key'])
      
      # Delete from Qdrant
      # docs for nested keys: https://qdrant.tech/documentation/concepts/filtering/#nested-key
      # Qdrant "points" look like this: Record(id='000295ca-bd28-ac4a-6f8d-c245f7377f90', payload={'metadata': {'course_name': 'zotero-extreme', 'pagenumber_or_timestamp': 15, 'readable_filename': 'Dunlosky et al. - 2013 - Improving Students’ Learning With Effective Learni.pdf', 's3_path': 'courses/zotero-extreme/Dunlosky et al. - 2013 - Improving Students’ Learning With Effective Learni.pdf'}, 'page_content': '18  \nDunlosky et al.\n3.3 Effects in representative educational contexts. Sev-\neral of the large summarization-training studies have been \nconducted in regular classrooms, indicating the feasibility of \ndoing so. For example, the study by A. King (1992) took place \nin the context of a remedial study-skills course for undergrad-\nuates, and the study by Rinehart et al. (1986) took place in \nsixth-grade classrooms, with the instruction led by students \nregular teachers. In these and other cases, students benefited \nfrom the classroom training. We suspect it may actually be \nmore feasible to conduct these kinds of training studies in \nclassrooms than in the laboratory, given the nature of the time \ncommitment for students. Even some of the studies that did \nnot involve training were conducted outside the laboratory; for \nexample, in the Bednall and Kehoe (2011) study on learning \nabout logical fallacies from Web modules (see data in Table 3), \nthe modules were actually completed as a homework assign-\nment. Overall, benefits can be observed in classroom settings; \nthe real constraint is whether students have the skill to suc-\ncessfully summarize, not whether summarization occurs in the \nlab or the classroom.\n3.4 Issues for implementation. Summarization would be \nfeasible for undergraduates or other learners who already \nknow how to summarize. For these students, summarization \nwould constitute an easy-to-implement technique that would \nnot take a lot of time to complete or understand. The only \nconcern would be whether these students might be better \nserved by some other strategy, but certainly summarization \nwould be better than the study strategies students typically \nfavor, such as highlighting and rereading (as we discuss in the \nsections on those strategies below). A trickier issue would \nconcern implementing the strategy with students who are not \nskilled summarizers. Relatively intensive training programs \nare required for middle school students or learners with learn-\ning disabilities to benefit from summarization. Such efforts \nare not misplaced; training has been shown to benefit perfor-\nmance on a range of measures, although the training proce-\ndures do raise practical issues (e.g., Gajria & Salvia, 1992: \n6.511 hours of training used for sixth through ninth graders \nwith learning disabilities; Malone & Mastropieri, 1991: 2 \ndays of training used for middle school students with learning \ndisabilities; Rinehart et al., 1986: 4550 minutes of instruc-\ntion per day for 5 days used for sixth graders). Of course, \ninstructors may want students to summarize material because \nsummarization itself is a goal, not because they plan to use \nsummarization as a study technique, and that goal may merit \nthe efforts of training.\nHowever, if the goal is to use summarization as a study \ntechnique, our question is whether training students would be \nworth the amount of time it would take, both in terms of the \ntime required on the part of the instructor and in terms of the \ntime taken away from students other activities. For instance, \nin terms of efficacy, summarization tends to fall in the middle \nof the pack when compared to other techniques. In direct \ncomparisons, it was sometimes more useful than rereading \n(Rewey, Dansereau, & Peel, 1991) and was as useful as note-\ntaking (e.g., Bretzing & Kulhavy, 1979) but was less powerful \nthan generating explanations (e.g., Bednall & Kehoe, 2011) or \nself-questioning (A. King, 1992).\n3.5 Summarization: Overall assessment. On the basis of the \navailable evidence, we rate summarization as low utility. It can \nbe an effective learning strategy for learners who are already \nskilled at summarizing; however, many learners (including \nchildren, high school students, and even some undergraduates) \nwill require extensive training, which makes this strategy less \nfeasible. Our enthusiasm is further dampened by mixed find-\nings regarding which tasks summarization actually helps. \nAlthough summarization has been examined with a wide \nrange of text materials, many researchers have pointed to fac-\ntors of these texts that seem likely to moderate the effects of \nsummarization (e.g'}, vector=None),
      self.qdrant_client.delete(
          collection_name=os.getenv('QDRANT_COLLECTION_NAME'),
          points_selector=models.Filter(
              must=[
                  models.FieldCondition(
                      key="metadata.course_name", 
                      match=models.MatchValue(value=course_name),
                  ),
              ]
          ),
      )
      
      # Delete from Supabase
      response = self.supabase_client.from_(os.getenv('MATERIALS_SUPABASE_TABLE')).delete().eq('metadata->>course_name', course_name).execute()
      print("supabase response: ", response)
      return "Success"
    except Exception as e:
      err: str = f"ERROR IN delete_entire_course(): Traceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:{e}"  # type: ignore
      print(err)
      return err

  # Create a method to delete file from s3, delete vector from qdrant, and delete row from supabase
  def delete_data(self, s3_path: str, course_name: str):
    """Delete file from S3, Qdrant, and Supabase."""
    print(f"Deleting {s3_path} from S3, Qdrant, and Supabase for course {course_name}")
    try:
      # Delete file from S3
      bucket_name = os.getenv('S3_BUCKET_NAME')
      self.s3_client.delete_object(Bucket=bucket_name, Key=s3_path)

      # Delete from Qdrant
      # docs for nested keys: https://qdrant.tech/documentation/concepts/filtering/#nested-key
      # Qdrant "points" look like this: Record(id='000295ca-bd28-ac4a-6f8d-c245f7377f90', payload={'metadata': {'course_name': 'zotero-extreme', 'pagenumber_or_timestamp': 15, 'readable_filename': 'Dunlosky et al. - 2013 - Improving Students’ Learning With Effective Learni.pdf', 's3_path': 'courses/zotero-extreme/Dunlosky et al. - 2013 - Improving Students’ Learning With Effective Learni.pdf'}, 'page_content': '18  \nDunlosky et al.\n3.3 Effects in representative educational contexts. Sev-\neral of the large summarization-training studies have been \nconducted in regular classrooms, indicating the feasibility of \ndoing so. For example, the study by A. King (1992) took place \nin the context of a remedial study-skills course for undergrad-\nuates, and the study by Rinehart et al. (1986) took place in \nsixth-grade classrooms, with the instruction led by students \nregular teachers. In these and other cases, students benefited \nfrom the classroom training. We suspect it may actually be \nmore feasible to conduct these kinds of training studies in \nclassrooms than in the laboratory, given the nature of the time \ncommitment for students. Even some of the studies that did \nnot involve training were conducted outside the laboratory; for \nexample, in the Bednall and Kehoe (2011) study on learning \nabout logical fallacies from Web modules (see data in Table 3), \nthe modules were actually completed as a homework assign-\nment. Overall, benefits can be observed in classroom settings; \nthe real constraint is whether students have the skill to suc-\ncessfully summarize, not whether summarization occurs in the \nlab or the classroom.\n3.4 Issues for implementation. Summarization would be \nfeasible for undergraduates or other learners who already \nknow how to summarize. For these students, summarization \nwould constitute an easy-to-implement technique that would \nnot take a lot of time to complete or understand. The only \nconcern would be whether these students might be better \nserved by some other strategy, but certainly summarization \nwould be better than the study strategies students typically \nfavor, such as highlighting and rereading (as we discuss in the \nsections on those strategies below). A trickier issue would \nconcern implementing the strategy with students who are not \nskilled summarizers. Relatively intensive training programs \nare required for middle school students or learners with learn-\ning disabilities to benefit from summarization. Such efforts \nare not misplaced; training has been shown to benefit perfor-\nmance on a range of measures, although the training proce-\ndures do raise practical issues (e.g., Gajria & Salvia, 1992: \n6.511 hours of training used for sixth through ninth graders \nwith learning disabilities; Malone & Mastropieri, 1991: 2 \ndays of training used for middle school students with learning \ndisabilities; Rinehart et al., 1986: 4550 minutes of instruc-\ntion per day for 5 days used for sixth graders). Of course, \ninstructors may want students to summarize material because \nsummarization itself is a goal, not because they plan to use \nsummarization as a study technique, and that goal may merit \nthe efforts of training.\nHowever, if the goal is to use summarization as a study \ntechnique, our question is whether training students would be \nworth the amount of time it would take, both in terms of the \ntime required on the part of the instructor and in terms of the \ntime taken away from students other activities. For instance, \nin terms of efficacy, summarization tends to fall in the middle \nof the pack when compared to other techniques. In direct \ncomparisons, it was sometimes more useful than rereading \n(Rewey, Dansereau, & Peel, 1991) and was as useful as note-\ntaking (e.g., Bretzing & Kulhavy, 1979) but was less powerful \nthan generating explanations (e.g., Bednall & Kehoe, 2011) or \nself-questioning (A. King, 1992).\n3.5 Summarization: Overall assessment. On the basis of the \navailable evidence, we rate summarization as low utility. It can \nbe an effective learning strategy for learners who are already \nskilled at summarizing; however, many learners (including \nchildren, high school students, and even some undergraduates) \nwill require extensive training, which makes this strategy less \nfeasible. Our enthusiasm is further dampened by mixed find-\nings regarding which tasks summarization actually helps. \nAlthough summarization has been examined with a wide \nrange of text materials, many researchers have pointed to fac-\ntors of these texts that seem likely to moderate the effects of \nsummarization (e.g'}, vector=None),
      self.qdrant_client.delete(
          collection_name=os.getenv('QDRANT_COLLECTION_NAME'),
          points_selector=models.Filter(must=[
              models.FieldCondition(
                  key="metadata.s3_path",
                  match=models.MatchValue(value=s3_path),
              ),
          ]),
      )

      # Delete from Supabase
      response = self.supabase_client.from_(os.getenv('MATERIALS_SUPABASE_TABLE')).delete().eq('metadata->>s3_path', s3_path).eq(
          'metadata->>course_name', course_name).execute()
      return "Success"
    except Exception as e:
      err: str = f"ERROR IN delete_data: Traceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:{e}"  # type: ignore
      print(err)
      return err

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
    response = self.supabase_client.table(os.getenv('MATERIALS_SUPABASE_TABLE')).select(
        'metadata->>course_name, metadata->>s3_path, metadata->>readable_filename').eq(  # type: ignore
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
      # TODO: change back to 50+ once we have bigger qdrant DB.
      top_n = 80 # HARD CODE TO ENSURE WE HIT THE MAX TOKENS
      start_time_overall = time.monotonic()
      found_docs = self.vectorstore.similarity_search(search_query, k=top_n, filter={'course_name': course_name})
      if len(found_docs) == 0:
        return []
      
      pre_prompt = "Please answer the following question. Use the context below, called your documents, only if it's helpful and don't use parts that are very irrelevant. It's good to quote from your documents directly, when you do always use Markdown footnotes for citations. Use react-markdown superscript to number the sources at the end of sentences (1, 2, 3...) and use react-markdown Footnotes to list the full document names for each number. Use ReactMarkdown aka 'react-markdown' formatting for super script citations, use semi-formal style. Feel free to say you don't know. \nHere's a few passages of the high quality documents:\n"
      
      # count tokens at start and end, then also count each context.
      token_counter, _ = count_tokens_and_cost(pre_prompt + '\n\nNow please respond to my query: ' + search_query)
      valid_docs = []
      for d in found_docs:
        doc_string = f"Document: {d.metadata['readable_filename']}{', page: ' + str(d.metadata['pagenumber_or_timestamp']) if d.metadata['pagenumber_or_timestamp'] else ''}\n{d.page_content}\n"
        num_tokens, prompt_cost = count_tokens_and_cost(doc_string)
        # print(f"token_counter: {token_counter}, num_tokens: {num_tokens}, max_tokens: {token_limit}")
        if token_counter + num_tokens <= token_limit:
          token_counter += num_tokens
          valid_docs.append(d)
        else:
          break
      
      print(f"Total tokens: {token_counter} total docs: {len(found_docs)} num docs used: {len(valid_docs)}")
      print(f"Course: {course_name} ||| search_query: {search_query}")
      print(f"⏰ ^^ Runtime of getTopContexts: {(time.monotonic() - start_time_overall):.2f} seconds")

      return self.format_for_json(valid_docs)
    except Exception as e:
      # return full traceback to front end
      err: str = f"In /getTopContexts. Course: {course_name} ||| search_query: {search_query}\nTraceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:\n{e}"  # type: ignore
      print(err)
      return err
  
  def get_stuffed_prompt(self, search_query: str, course_name: str, token_limit: int = 7_000) -> str:
    """
    Returns
      String: A fully formatted prompt string.
    """
    try:
      top_n = 150
      start_time_overall = time.monotonic()
      found_docs = self.vectorstore.similarity_search(search_query, k=top_n, filter={'course_name': course_name})
      if len(found_docs) == 0:
        return search_query
      
      pre_prompt = "Please answer the following question. Use the context below, called your documents, only if it's helpful and don't use parts that are very irrelevant. It's good to quote from your documents directly, when you do always use Markdown footnotes for citations. Use react-markdown superscript to number the sources at the end of sentences (1, 2, 3...) and use react-markdown Footnotes to list the full document names for each number. Use ReactMarkdown aka 'react-markdown' formatting for super script citations, use semi-formal style. Feel free to say you don't know. \nHere's a few passages of the high quality documents:\n"
      
      # count tokens at start and end, then also count each context.
      token_counter, _ = count_tokens_and_cost(pre_prompt + '\n\nNow please respond to my query: ' + search_query)
      valid_docs = []
      for d in found_docs:
        doc_string = f"---\nDocument: {d.metadata['readable_filename']}{', page: ' + str(d.metadata['pagenumber_or_timestamp']) if d.metadata['pagenumber_or_timestamp'] else ''}\n{d.page_content}\n"
        num_tokens, prompt_cost = count_tokens_and_cost(doc_string)
        print(f"Page: {d.page_content[:100]}...")
        print(f"token_counter: {token_counter}, num_tokens: {num_tokens}, token_limit: {token_limit}")
        if token_counter + num_tokens <= token_limit:
          token_counter += num_tokens
          valid_docs.append(d)
        else:
          continue
          print("running continue")
        
      # Convert the valid_docs to full prompt
      separator = '---\n' # between each context
      context_text = separator.join(
          f"Document: {d.metadata['readable_filename']}{', page: ' + str(d.metadata['pagenumber_or_timestamp']) if d.metadata['pagenumber_or_timestamp'] else ''}\n{d.page_content}\n"
          for d in valid_docs
      )

      # Create the stuffedPrompt
      stuffedPrompt = (
        pre_prompt +
        context_text +
        '\n\nNow please respond to my query: ' +
        search_query
      )

      TOTAL_num_tokens, prompt_cost = count_tokens_and_cost(stuffedPrompt, openai_model_name='gpt-4')
      print(f"Total tokens: {TOTAL_num_tokens}, prompt_cost: {prompt_cost}")
      print("total docs: ", len(found_docs))
      print("num docs used: ", len(valid_docs))

      print(f"⏰ ^^ Runtime of getTopContexts: {(time.monotonic() - start_time_overall):.2f} seconds")
      return stuffedPrompt
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