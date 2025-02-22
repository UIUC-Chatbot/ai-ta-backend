import beam

from typing import Any, Callable, Dict, List, Optional, Union, cast

import beam
from beam import QueueDepthAutoscaler  # RequestLatencyAutoscaler,
from beam import BotContext  # To obtain task_id 

if beam.env.is_remote():
  # Only import these in the Cloud container, not when building the container.
  import asyncio
  import inspect
  import json
  import logging
  import mimetypes
  import os
  import re
  import shutil
  import subprocess
  import time
  import traceback
  import uuid
  from pathlib import Path
  from tempfile import NamedTemporaryFile

  # from typing import Any, Callable, Dict, List, Optional, Union
  import beam
  import boto3
  import fitz # type: ignore
  import openai
  import pdfplumber # type: ignore
  import pytesseract # type: ignore
  import sentry_sdk
  import supabase
  from bs4 import BeautifulSoup # type: ignore
  from git.repo import Repo # type: ignore
  from langchain.document_loaders import (
      Docx2txtLoader,
      GitLoader,
      PythonLoader,
      TextLoader,
      UnstructuredExcelLoader,
      UnstructuredPowerPointLoader,
  )
  from langchain.document_loaders.csv_loader import CSVLoader
  from langchain.embeddings.openai import OpenAIEmbeddings
  from langchain.schema import Document
  from langchain.text_splitter import RecursiveCharacterTextSplitter
  from langchain.vectorstores import Qdrant
  from OpenaiEmbeddings import OpenAIAPIProcessor
  from PIL import Image
  from posthog import Posthog
  from pydub import AudioSegment # type: ignore
  from qdrant_client import QdrantClient, models
  from qdrant_client.models import PointStruct
  from requests.exceptions import Timeout
  from supabase.client import ClientOptions

  sentry_sdk.init(
      dsn=os.getenv("SENTRY_DSN"),
      # Set traces_sample_rate to 1.0 to capture 100% of transactions for performance monitoring.
      traces_sample_rate=1.0,
      # Set profiles_sample_rate to 1.0 to profile 100% of sampled transactions.
      # We recommend adjusting this value in production.
      profiles_sample_rate=1.0,
      enable_tracing=True)

requirements = [
    "openai<1.0",
    "pandas",
    "supabase==2.5.3",
    "tiktoken==0.5.1",
    "boto3==1.28.79",
    "qdrant-client==1.7.3",
    "langchain==0.0.331",
    "posthog==3.1.0",
    "pysrt==1.1.2",
    "docx2txt==0.8",
    "pydub==0.25.1",
    "ffmpeg-python==0.2.0",
    "ffprobe==0.5",
    "ffmpeg==1.4",
    "PyMuPDF==1.23.6",
    "pytesseract==0.3.10",  # image OCR
    "openpyxl==3.1.2",  # excel
    "networkx==3.2.1",  # unused part of excel partitioning :(
    "python-pptx==0.6.23",
    "unstructured==0.15.12",
    "GitPython==3.1.40",
    "beautifulsoup4==4.12.2",
    "sentry-sdk==1.39.1",
    "pdfplumber==0.11.0",  # PDF OCR, better performance than Fitz/PyMuPDF in my Gies PDF testing.
]

image = (beam.Image(
    python_version="python3.10",
    commands=(["apt-get update && apt-get install -y ffmpeg tesseract-ocr"]),
    python_packages=requirements,
))

autoscaler = QueueDepthAutoscaler(tasks_per_container=300, max_containers=3)

ourSecrets = [
    "SUPABASE_URL",
    "SUPABASE_API_KEY",
    "VLADS_OPENAI_KEY",
    "REFACTORED_MATERIALS_SUPABASE_TABLE",
    "S3_BUCKET_NAME",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "QDRANT_COLLECTION_NAME",
    "OPENAI_API_TYPE",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "POSTHOG_API_KEY",
    # "AZURE_OPENAI_KEY",
    # "AZURE_OPENAI_ENGINE",
    # "AZURE_OPENAI_KEY",
    # "AZURE_OPENAI_ENDPOINT",
]

def loader():
  """
  The loader function will run once for each worker that starts up. https://docs.beam.cloud/deployment/loaders
  """
  openai.api_key = os.getenv("VLADS_OPENAI_KEY")

  # vector DB
  qdrant_client = QdrantClient(
      url=os.getenv('QDRANT_URL'),
      api_key=os.getenv('QDRANT_API_KEY'),
  )

  vectorstore = Qdrant(
      client=qdrant_client,
      collection_name=os.environ['QDRANT_COLLECTION_NAME'],
      embeddings=OpenAIEmbeddings(
          openai_api_type=os.environ['OPENAI_API_TYPE'],  # "openai" or "azure"
          openai_api_key=os.getenv('VLADS_OPENAI_KEY')))

  # S3
  s3_client = boto3.client(
      's3',
      aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
  )

  # Create a Supabase client
  supabase_client = supabase.create_client(  # type: ignore
      supabase_url=os.environ['SUPABASE_URL'],
      supabase_key=os.environ['SUPABASE_API_KEY'],
      options=ClientOptions(postgrest_client_timeout=60,))

  # llm = AzureChatOpenAI(
  #     temperature=0,
  #     deployment_name=os.getenv('AZURE_OPENAI_ENGINE'),  #type:ignore
  #     openai_api_base=os.getenv('AZURE_OPENAI_ENDPOINT'),  #type:ignore
  #     openai_api_key=os.getenv('AZURE_OPENAI_KEY'),  #type:ignore
  #     openai_api_version=os.getenv('OPENAI_API_VERSION'),  #type:ignore
  #     openai_api_type=OPENAI_API_TYPE)

  posthog = Posthog(sync_mode=True, project_api_key=os.environ['POSTHOG_API_KEY'], host='https://app.posthog.com')

  return qdrant_client, vectorstore, s3_client, supabase_client, posthog

@beam.task_queue(name='firecrawl_ingest_task_queue',
                 workers=4,
                 cpu=1,
                 memory=3_072,
                 max_pending_tasks=15_000,
                # DEPRICATED, not needed -- callback_url='https://uiuc.chat/api/UIUC-api/ingestTaskCallback',
                 timeout=60 * 25,
                 retries=1,
                 secrets=ourSecrets,
                 on_start=loader,
                 image=image,
                 autoscaler=autoscaler)
def ingest(context, **inputs: Dict[str | List[str], Any]):
    qdrant_client, vectorstore, s3_client, supabase_client, posthog = context.on_start_value
    course_name: List[str] | str = cast(Union[List[str], str], inputs.get('course_name', ''))
    s3_paths: List[str] | str = cast(Union[List[str], str], inputs.get('s3_paths', ''))
    url: List[str] | str | None = cast(Union[List[str], str, None], inputs.get('url', None))
    base_url: List[str] | str | None = cast(Union[List[str], str, None], inputs.get('base_url', None))
    readable_filename: List[str] | str = cast(Union[List[str], str], inputs.get('readable_filename', ''))
    content: str | List[str] | None = cast(Union[str, List[str], None], inputs.get('content', None))
    doc_groups: List[str] | str = cast(Union[List[str], str], inputs.get('groups', []))

    print(f"In top of /ingest route. course: {course_name}, s3paths: {s3_paths}, readable_filename: {readable_filename}, base_url: {base_url}, url: {url}, content: {content}, doc_groups: {doc_groups}")

    ingester = Ingest(qdrant_client, vectorstore, s3_client, supabase_client, posthog)

    def run_ingest(course_name, s3_paths, base_url, url, readable_filename, content, groups):
        if content:
            return ingester.ingest_single_web_text(course_name, base_url, url, content, readable_filename, groups=groups)
        elif readable_filename == '':
            return ingester.bulk_ingest(course_name, s3_paths, base_url=base_url, url=url, groups=groups)
        else:
            return ingester.bulk_ingest(course_name, s3_paths, readable_filename=readable_filename, base_url=base_url, url=url, groups=groups)

    success_fail_dict = {}
    try:
        success_fail_dict = run_ingest(course_name, s3_paths, base_url, url, readable_filename, content, doc_groups)
    except Exception as e:
        # Don't bother retrying
        print("Exception in main ingest", e)
        success_fail_dict = {'failure_ingest': str(e)}
        handle_ingest_failure(supabase_client, posthog, course_name, s3_paths, readable_filename, url, base_url, e)
    
        # Cleanup: Remove from docs_in_progress table
    try:
        if base_url:
            print('Removing URL-based document from in_progress')
            supabase_client.table('documents_in_progress').delete()\
                .eq('url', url)\
                .eq('base_url', base_url)\
                .execute()
        else:
            supabase_client.table('documents_in_progress').delete()\
                .eq('course_name', course_name)\
                .eq('s3_path', s3_paths)\
                .eq('readable_filename', readable_filename)\
                .execute()
    except Exception as e:
        print(f"Error cleaning up documents_in_progress: {e}")
        sentry_sdk.capture_exception(e)
        
    if success_fail_dict.get('success_ingest'):
      posthog.capture(
          'distinct_id_of_the_user',
          event='ingest_success',
          properties={
              'course_name': course_name,
              's3_path': s3_paths,
              's3_paths': s3_paths,
              'url': url,
              'base_url': base_url,
              'readable_filename': readable_filename,
              'content': content,
              'doc_groups': doc_groups,
          })
        
    
    print(f"Final success_fail_dict: {success_fail_dict}")
    sentry_sdk.flush(timeout=20)
    return json.dumps(success_fail_dict)


def handle_ingest_failure(supabase_client, posthog, course_name, s3_paths, readable_filename, url, base_url, error):
    document = {
        "course_name": course_name,
        "s3_path": s3_paths,
        "readable_filename": readable_filename,
        "url": url,
        "base_url": base_url,
        "error": str(error)
    }
    # Check if document already exists
    existing = supabase_client.table('documents_failed')\
        .select('*')\
        .eq('course_name', course_name)\
        .eq('s3_path', s3_paths)\
        .eq('readable_filename', readable_filename)\
        .eq('url', url)\
        .eq('base_url', base_url)\
        .execute()
    
    # Only insert if no matching document exists
    if not existing.data:
        supabase_client.table('documents_failed').insert(document).execute()

    posthog.capture(
                'distinct_id_of_the_user',
                event='ingest_failure',
                properties={
                    'course_name':
                        course_name,
                    's3_path':
                        s3_paths,
                    'url':
                        url,
                    'base_url': base_url,
                    'readable_filename': readable_filename,
                    'error': str(error)
                })


class Ingest():

    def __init__(self, qdrant_client, vectorstore, s3_client, supabase_client, posthog):
        self.qdrant_client = qdrant_client
        self.vectorstore = vectorstore
        self.s3_client = s3_client
        self.supabase_client = supabase_client
        self.posthog = posthog

    def bulk_ingest(self, course_name: str, s3_paths: Union[str, List[str]],
                   **kwargs) -> Dict[str, None | str | Dict[str, str]]:
        """ 
        Bulk ingest a list of s3 paths into the vectorstore, and also into the supabase database.
        -> Dict[str, str | Dict[str, str]]
        """
        print('s3 path from bulk ingest', s3_paths)
        success_status: Dict[str, None | str | Dict[str, str]] = {"success_ingest": None, "failure_ingest": None}

        def _ingest_single(ingest_method: Callable, s3_path: str, *args, **kwargs) -> None:
            """Handle running an arbitrary ingest function for an individual file."""
            # RUN INGEST METHOD
            ret = ingest_method(s3_path, *args, **kwargs)
            if ret == "Success":
                success_status['success_ingest'] = str(s3_path)
            else:
                success_status['failure_ingest'] = {'s3_path': str(s3_path), 'error': str(ret)}

        # 👇👇👇👇 ADD NEW INGEST METHODS HERE 👇👇👇👇🎉
        file_ingest_methods = {
            # '.html': self._ingest_html,
            # '.py': self._ingest_single_py,
            # '.pdf': self._ingest_single_pdf,
            '.txt': self._ingest_single_txt,
            '.md': self._ingest_single_txt,
            # '.srt': self._ingest_single_srt,
            # '.vtt': self._ingest_single_vtt,
            # '.docx': self._ingest_single_docx,
            # '.ppt': self._ingest_single_ppt,
            # '.pptx': self._ingest_single_ppt,
            # '.xlsx': self._ingest_single_excel,
            # '.xls': self._ingest_single_excel,
            # '.xlsm': self._ingest_single_excel,
            # '.xlsb': self._ingest_single_excel,
            # '.xltx': self._ingest_single_excel,
            # '.xltm': self._ingest_single_excel,
            # '.xlt': self._ingest_single_excel,
            # '.xml': self._ingest_single_excel,
            # '.xlam': self._ingest_single_excel,
            # '.xla': self._ingest_single_excel,
            # '.xlw': self._ingest_single_excel,
            # '.xlr': self._ingest_single_excel,
            # '.csv': self._ingest_single_csv,
            # '.png': self._ingest_single_image,
            # '.jpg': self._ingest_single_image,
        }

        # Ingest methods via MIME type (more general than filetype)
        mimetype_ingest_methods = {
            # 'video': self._ingest_single_video,
            # 'audio': self._ingest_single_video,
            'text': self._ingest_single_txt,
            # 'image': self._ingest_single_image,
        }
        # 👆👆👆👆 ADD NEW INGEST METHODS HERE 👆👆👆👆🎉

        print(f"Top of ingest, Course_name {course_name}. S3 paths {s3_paths}")
        try:
            if isinstance(s3_paths, str):
                s3_paths = [s3_paths]

            for s3_path in s3_paths:
                file_extension = Path(s3_path).suffix
                with NamedTemporaryFile(suffix=file_extension) as tmpfile:
                    self.s3_client.download_fileobj(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_path, Fileobj=tmpfile)
                    mime_type = str(mimetypes.guess_type(tmpfile.name, strict=False)[0])
                    mime_category = mime_type.split('/')[0] if '/' in mime_type else mime_type

                if file_extension in file_ingest_methods:
                    # Use specialized functions when possible, fallback to mimetype. Else raise error.
                    ingest_method = file_ingest_methods[file_extension]
                    _ingest_single(ingest_method, s3_path, course_name, **kwargs)
                elif mime_category in mimetype_ingest_methods:
                    # fallback to MimeType
                    print("mime category", mime_category)
                    ingest_method = mimetype_ingest_methods[mime_category]
                    _ingest_single(ingest_method, s3_path, course_name, **kwargs)
                else:
                    # No supported ingest... Fallback to attempting utf-8 decoding, otherwise fail.
                    try:
                        self._ingest_single_txt(s3_path, course_name, **kwargs)
                        success_status['success_ingest'] = s3_path
                        print(f"No ingest methods -- Falling back to UTF-8 INGEST... s3_path = {s3_path}")
                    except Exception as e:
                        sentry_sdk.capture_exception(e)
                        print(
                            f"We don't have a ingest method for this filetype: {file_extension}. As a last-ditch effort, we tried to ingest the file as utf-8 text, but that failed too. File is unsupported: {s3_path}. UTF-8 ingest error: {e}"
                        )
                        success_status['failure_ingest'] = {
                            's3_path':
                                s3_path,
                            'error':
                                f"We don't have a ingest method for this filetype: {file_extension} (with generic type {mime_type}), for file: {s3_path}"
                        }
                        self.posthog.capture(
                            'distinct_id_of_the_user',
                            event='ingest_failure',
                            properties={
                                'course_name': course_name,
                                's3_path': s3_paths,
                                'kwargs': kwargs,
                                'error':
                                    f"We don't have a ingest method for this filetype: {file_extension} (with generic type {mime_type}), for file: {s3_path}"
                            })

            return success_status
        except Exception as e:
            frame = inspect.currentframe()
            if frame is None:
                code_name = "unknown"
            else:
                code_name = frame.f_code.co_name
            err = f"❌❌ Error in /ingest: `{code_name}`: {e}\nTraceback:\n", traceback.format_exc()
            sentry_sdk.capture_exception(e)

            success_status['failure_ingest'] = {'s3_path': s3_path, 'error': f"MAJOR ERROR DURING INGEST: {err}"}
            self.posthog.capture('distinct_id_of_the_user',
                               event='ingest_failure',
                               properties={
                                   'course_name': course_name,
                                   's3_path': s3_paths,
                                   'kwargs': kwargs,
                                   'error': err
                               })

            sentry_sdk.capture_exception(e)
            print(f"MAJOR ERROR IN /bulk_ingest: {str(e)}")
            return success_status

    def delete_data(self, course_name: str, s3_path: str, source_url: str) -> str:
        """Delete file from S3, Qdrant, and Supabase.
        
        Args:
            course_name (str): Name of the course
            s3_path (str): S3 path of the file to delete
            source_url (str): URL of the file to delete
            
        Returns:
            str: "Success" or error message
        """
        print(f"Deleting {s3_path or source_url} from S3, Qdrant, and Supabase for course {course_name}")
        try:
            # Delete files by S3 path
            if s3_path:
                # Delete from S3
                try:
                    bucket_name = os.environ['S3_BUCKET_NAME']
                    self.s3_client.delete_object(Bucket=bucket_name, Key=s3_path)
                except Exception as e:
                    print("Error in deleting file from s3:", e)
                    sentry_sdk.capture_exception(e)

                # Delete from Qdrant
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

                # Delete from Supabase
                try:
                    self.supabase_client.table(os.environ['REFACTORED_MATERIALS_SUPABASE_TABLE']).delete().eq(
                        's3_path', s3_path).eq('course_name', course_name).execute()
                except Exception as e:
                    print("Error in deleting file from supabase:", e)
                    sentry_sdk.capture_exception(e)

            # Delete files by their URL identifier
            elif source_url:
                # Delete from Qdrant
                try:
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

                # Delete from Supabase
                try:
                    self.supabase_client.table(os.environ['REFACTORED_MATERIALS_SUPABASE_TABLE']).delete().eq(
                        'url', source_url).eq('course_name', course_name).execute()
                except Exception as e:
                    print("Error in deleting file from supabase:", e)
                    sentry_sdk.capture_exception(e)

            return "Success"
        except Exception as e:
            frame = inspect.currentframe()
            if frame is None:
                code_name = "unknown"
            else:
                code_name = frame.f_code.co_name
            err: str = f"ERROR IN delete_data: Traceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {code_name}:{e}"  # type: ignore
            print(err)
            sentry_sdk.capture_exception(e)
            return err

    def check_for_duplicates(self, texts: List[Dict], metadatas: List[Dict[str, Any]]) -> bool:
        """
        For given metadata, fetch docs from Supabase based on S3 path or URL.
        If docs exists, concatenate the texts and compare with current texts, if same, return True.
        """
        doc_table = os.getenv('REFACTORED_MATERIALS_SUPABASE_TABLE')
        course_name = metadatas[0]['course_name']
        incoming_s3_path = metadatas[0]['s3_path']
        url = metadatas[0]['url']

        if incoming_s3_path:
            # check if uuid exists in s3_path -- not all s3_paths have uuids!
            incoming_filename = incoming_s3_path.split('/')[-1]
            # print("Full filename: ", incoming_filename)
            pattern = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}',
                               re.I)  # uuid V4 pattern, and v4 only.
            if bool(pattern.search(incoming_filename)):
                # uuid pattern exists -- remove the uuid and proceed with duplicate checking
                original_filename = incoming_filename[37:]
            else:
                # do not remove anything and proceed with duplicate checking
                original_filename = incoming_filename
            print(f"Filename after removing uuid: {original_filename}")

            supabase_contents = self.supabase_client.table(doc_table).select('id', 'contexts', 's3_path').eq(
                'course_name', course_name).like('s3_path', '%' + original_filename + '%').order('id', desc=True).execute()
            supabase_contents = supabase_contents.data
            print(f"No. of S3 path based records retrieved: {len(supabase_contents)}"
                )  # multiple records can be retrieved: 3.pdf and 453.pdf

        elif url:
            original_filename = url
            supabase_contents = self.supabase_client.table(doc_table).select('id', 'contexts', 'url').eq(
                'course_name', course_name).eq('url', url).order('id', desc=True).execute()
            supabase_contents = supabase_contents.data
            print(f"No. of URL-based records retrieved: {len(supabase_contents)}")
        else:
            original_filename = None
            supabase_contents = []

        supabase_whole_text = ""
        exact_doc_exists = False
        supabase_contexts = None

        if len(supabase_contents) > 0:  # a doc with same filename exists in Supabase
            for record in supabase_contents:
                if incoming_s3_path:
                    curr_filename = record['s3_path'].split('/')[-1]
                    older_s3_path = record['s3_path']
                    if bool(pattern.search(curr_filename)):
                        # uuid pattern exists -- remove the uuid and proceed with duplicate checking
                        sql_filename = curr_filename[37:]
                    else:
                        # do not remove anything and proceed with duplicate checking
                        sql_filename = curr_filename
                elif url:
                    print("URL retrieved from SQL: ", record.keys())
                    sql_filename = record['url']
                else:
                    continue
                print("Original filename: ", original_filename, "Current SQL filename: ", sql_filename)

                if original_filename == sql_filename:  # compare og s3_path/url with incoming s3_path/url
                    supabase_contexts = record
                    exact_doc_exists = True
                    print("Exact doc exists in Supabase:", sql_filename)
                    break

            if exact_doc_exists and supabase_contexts is not None:
                # concatenate og texts
                for text in supabase_contexts['contexts']:
                    supabase_whole_text += text['text']

                current_whole_text = ""
                for text in texts:
                    current_whole_text += text['input']

                if supabase_whole_text == current_whole_text:  # matches the previous file
                    print(f"Duplicate ingested! 📄 s3_path/url: {original_filename}.")
                    return True
                else:  # the file is updated
                    print(f"Updated file detected! Same filename, new contents. 📄s3_path/url: {original_filename}")

                    # call the delete function on older doc
                    print("older s3_path/url to be deleted: ", sql_filename)
                    if incoming_s3_path:
                        delete_status = self.delete_data(course_name, older_s3_path, '')
                    else:
                        delete_status = self.delete_data(course_name, '', url)
                    print("delete_status: ", delete_status)
                    return False
            else:
                print(f"NOT a duplicate! 📄s3_path: {original_filename}")
                return False
        else:  # filename does not already exist in Supabase, so its a brand new file
            print(f"NOT a duplicate! 📄s3_path: {original_filename}")
            return False

    def _ingest_single_txt(self, s3_path: str, course_name: str, **kwargs) -> str:
        """Ingest a single .txt or .md file from S3.
        Args:
            s3_path (str): A path to a .txt file in S3
            course_name (str): The name of the course
        Returns:
            str: "Success" or an error message
        """
        print("In text ingest, UTF-8")
        print("kwargs", kwargs)
        try:
            # NOTE: slightly different method for .txt files, no need for download. It's part of the 'body'
            response = self.s3_client.get_object(Bucket=os.environ['S3_BUCKET_NAME'], Key=s3_path)
            text = response['Body'].read().decode('utf-8', errors='ignore')
            print("UTF-8 text to ignest (from s3)", text)
            text = [text]

            metadatas: List[Dict[str, Any]] = [{
                'course_name': course_name,
                's3_path': s3_path,
                'readable_filename': kwargs.get('readable_filename',
                                              Path(s3_path).name[37:]),
                'pagenumber': '',
                'timestamp': '',
                'url': kwargs.get('url', ''),
                'base_url': kwargs.get('base_url', '')
            }]
            print("Prior to ingest", metadatas)

            success_or_failure = self.split_and_upload(texts=text, metadatas=metadatas, **kwargs)
            return success_or_failure
        except Exception as e:
            frame = inspect.currentframe()
            if frame is None:
                code_name = "unknown"
            else:
                code_name = frame.f_code.co_name
            err = f"❌❌ Error in (TXT ingest): `{code_name}`: {e}\nTraceback:\n", traceback.format_exc()
            print(err)
            sentry_sdk.capture_exception(e)
            return str(err)

    def ingest_single_web_text(self, course_name: str, base_url: str, url: str, content: str, readable_filename: str,
                              **kwargs):
        """Crawlee integration
        """
        self.posthog.capture('distinct_id_of_the_user',
                           event='ingest_single_web_text_invoked',
                           properties={
                               'course_name': course_name,
                               'base_url': base_url,
                               'url': url,
                               'content': content,
                               'title': readable_filename
                           })
        success_or_failure: Dict[str, None | str | Dict[str, str]] = {"success_ingest": None, "failure_ingest": None}
        try:
            # if not, ingest the text
            text = [content]
            metadatas: List[Dict[str, Any]] = [{
                'course_name': course_name,
                's3_path': '',
                'readable_filename': readable_filename,
                'pagenumber': '',
                'timestamp': '',
                'url': url,
                'base_url': base_url,
            }]
            self.split_and_upload(texts=text, metadatas=metadatas, **kwargs)
            self.posthog.capture('distinct_id_of_the_user',
                               event='ingest_single_web_text_succeeded',
                               properties={
                                   'course_name': course_name,
                                   'base_url': base_url,
                                   'url': url,
                                   'title': readable_filename
                               })
            success_or_failure['success_ingest'] = url
            return success_or_failure
        except Exception as e:
            frame = inspect.currentframe()
            if frame is None:
                code_name = "unknown"
            else:
                code_name = frame.f_code.co_name
            err = f"❌❌ Error in (web text ingest): `{code_name}`: {e}\nTraceback:\n", traceback.format_exc()  # type: ignore
            print(err)
            sentry_sdk.capture_exception(e)
            success_or_failure['failure_ingest'] = {'url': url, 'error': str(err)}
            return success_or_failure

    def split_and_upload(self, texts: List[str], metadatas: List[Dict[str, Any]], **kwargs):
        """ This is usually the last step of document ingest. Chunk & upload to Qdrant (and Supabase.. todo).
            Takes in Text and Metadata (from Langchain doc loaders) and splits / uploads to Qdrant.

            good examples here: https://langchain.readthedocs.io/en/latest/modules/utils/combine_docs_examples/textsplitter.html

            Args:
                texts (List[str]): _description_
                metadatas (List[Dict[str, Any]]): _description_
        """
        print(f"In split and upload. Metadatas: {metadatas}")
        self.posthog.capture('distinct_id_of_the_user',
                           event='split_and_upload_invoked',
                           properties={
                               'course_name': metadatas[0].get('course_name', None),
                               's3_path': metadatas[0].get('s3_path', None),
                               'readable_filename': metadatas[0].get('readable_filename', None),
                               'url': metadatas[0].get('url', None),
                               'base_url': metadatas[0].get('base_url', None),
                           })

        #print(f"In split and upload. Metadatas: {metadatas}")
        #print(f"Texts: {texts}")
        assert len(texts) == len(
            metadatas
        ), f'must have equal number of text strings and metadata dicts. len(texts) is {len(texts)}. len(metadatas) is {len(metadatas)}'

        try:
            chunk_size = 2_000
            if metadatas[0].get('course_name') == 'GROWMARK-Crop-Protection-Guide':
                # Special case for this project, try to embed entire PDF page as 1 chunk (better at tables)
                chunk_size = 6_000

            text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                chunk_size=chunk_size,
                chunk_overlap=150,
                separators=[
                    "\n\n", "\n", ". ", " ", ""
                ]  # try to split on paragraphs... fallback to sentences, then chars, ensure we always fit in context window
            )
            contexts: List[Document] = text_splitter.create_documents(texts=texts, metadatas=metadatas)
            input_texts = [{'input': context.page_content, 'model': 'text-embedding-ada-002'} for context in contexts]

            # check for duplicates
            is_duplicate = self.check_for_duplicates(input_texts, metadatas)
            if is_duplicate:
                self.posthog.capture('distinct_id_of_the_user',
                                   event='split_and_upload_succeeded',
                                   properties={
                                       'course_name': metadatas[0].get('course_name', None),
                                       's3_path': metadatas[0].get('s3_path', None),
                                       'readable_filename': metadatas[0].get('readable_filename', None),
                                       'url': metadatas[0].get('url', None),
                                       'base_url': metadatas[0].get('base_url', None),
                                       'is_duplicate': True,
                                   })
                return "Success"

            # adding chunk index to metadata for parent doc retrieval
            print("GROUPS: ", kwargs.get('groups', ''))
            for i, context in enumerate(contexts):
                context.metadata['chunk_index'] = i
                context.metadata['doc_groups'] = kwargs.get('groups', [])

            print("Starting to call embeddings API")
            embeddings_start_time = time.monotonic()
            oai = OpenAIAPIProcessor(
                input_prompts_list=input_texts,
                request_url='https://api.openai.com/v1/embeddings',
                api_key=os.getenv('VLADS_OPENAI_KEY'),
                max_requests_per_minute=10_000,
                max_tokens_per_minute=10_000_000,
                max_attempts=1_000,
                logging_level=logging.INFO,
                token_encoding_name='cl100k_base')
            asyncio.run(oai.process_api_requests_from_file())
            print(f"⏰ embeddings runtime: {(time.monotonic() - embeddings_start_time):.2f} seconds")
            # parse results into dict of shape page_content -> embedding
            embeddings_dict: dict[str, List[float]] = {
                item[0]['input']: item[1]['data'][0]['embedding'] for item in oai.results
            }

            ### BULK upload to Qdrant ###
            vectors: list[PointStruct] = []
            for context in contexts:
                # !DONE: Updated the payload so each key is top level (no more payload.metadata.course_name. Instead, use payload.course_name), great for creating indexes.
                upload_metadata = {**context.metadata, "page_content": context.page_content}
                vectors.append(
                    PointStruct(id=str(uuid.uuid4()), vector=embeddings_dict[context.page_content], payload=upload_metadata))

            try:
                self.qdrant_client.upsert(
                    collection_name=os.environ['QDRANT_COLLECTION_NAME'],  # type: ignore
                    points=vectors,  # type: ignore
                )
            except Exception as e:
                logging.error("Error in QDRANT upload: ", exc_info=True)
                err = f"Error in QDRANT upload: {e}"
                if "timed out" in str(e):
                    # timed out error is fine, task will continue in background
                    pass
                else:
                    print(err)
                    sentry_sdk.capture_exception(e)
                    raise Exception(err)

            ### Supabase SQL ###
            contexts_for_supa = [{
                "text": context.page_content,
                "pagenumber": context.metadata.get('pagenumber'),
                "timestamp": context.metadata.get('timestamp'),
                "chunk_index": context.metadata.get('chunk_index'),
                "embedding": embeddings_dict[context.page_content]
            } for context in contexts]

            document = {
                "course_name": contexts[0].metadata.get('course_name'),
                "s3_path": contexts[0].metadata.get('s3_path'),
                "readable_filename": contexts[0].metadata.get('readable_filename'),
                "url": contexts[0].metadata.get('url'),
                "base_url": contexts[0].metadata.get('base_url'),
                "contexts": contexts_for_supa,
            }

            # Calculate the size of the document object in MB
            document_size_mb = len(json.dumps(document).encode('utf-8')) / (1024 * 1024)
            print(f"Document size: {document_size_mb:.2f} MB")

            response = self.supabase_client.table(
                os.getenv('REFACTORED_MATERIALS_SUPABASE_TABLE')).insert(document).execute()  # type: ignore

            # need to update Supabase tables with doc group info
            if len(response.data) > 0:
                # get groups from kwargs
                groups = kwargs.get('groups', '')
                if groups:
                    # call the supabase function to add the document to the group
                    if contexts[0].metadata.get('url'):
                        data, count = self.supabase_client.rpc(
                            'add_document_to_group_url', {
                                "p_course_name": contexts[0].metadata.get('course_name'),
                                "p_s3_path": contexts[0].metadata.get('s3_path'),
                                "p_url": contexts[0].metadata.get('url'),
                                "p_readable_filename": contexts[0].metadata.get('readable_filename'),
                                "p_doc_groups": groups,
                            }).execute()
                    else:
                        data, count = self.supabase_client.rpc(
                            'add_document_to_group', {
                                "p_course_name": contexts[0].metadata.get('course_name'),
                                "p_s3_path": contexts[0].metadata.get('s3_path'),
                                "p_url": contexts[0].metadata.get('url'),
                                "p_readable_filename": contexts[0].metadata.get('readable_filename'),
                                "p_doc_groups": groups,
                            }).execute()

                    if len(data) == 0:
                        print("Error in adding to doc groups")
                        raise ValueError("Error in adding to doc groups")

            self.posthog.capture('distinct_id_of_the_user',
                               event='split_and_upload_succeeded',
                               properties={
                                   'course_name': metadatas[0].get('course_name', None),
                                   's3_path': metadatas[0].get('s3_path', None),
                                   'readable_filename': metadatas[0].get('readable_filename', None),
                                   'url': metadatas[0].get('url', None),
                                   'base_url': metadatas[0].get('base_url', None),
                                   'is_duplicate': False,
                               })
            print("successful END OF split_and_upload")
            return "Success"
        except Exception as e:
            frame = inspect.currentframe()
            if frame is None:
                code_name = "unknown"
            else:
                code_name = frame.f_code.co_name
            err: str = f"ERROR IN split_and_upload(): Traceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {code_name}:{e}"  # type: ignore
            print(err)
            sentry_sdk.capture_exception(e)
            sentry_sdk.flush(timeout=20)
            raise Exception(err)

