import logging
import os
import time
from typing import List
from urllib.parse import quote_plus

from dotenv import load_dotenv
from flask import abort
from flask import Flask
from flask import jsonify
from flask import make_response
from flask import request
from flask import Response
from flask import send_from_directory
from flask_cors import CORS
from flask_executor import Executor
from flask_injector import FlaskInjector
from flask_injector import RequestScope
from injector import Binder
from injector import SingletonScope
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from sqlalchemy import inspect, text
import urllib3
from qdrant_client import QdrantClient, models
import boto3

from ai_ta_backend.database.aws import AWSStorage
from ai_ta_backend.database.qdrant import VectorDatabase
from ai_ta_backend.database.sql import SQLAlchemyDatabase
from ai_ta_backend.executors.flask_executor import ExecutorInterface
from ai_ta_backend.executors.flask_executor import FlaskExecutorAdapter
from ai_ta_backend.executors.process_pool_executor import \
    ProcessPoolExecutorAdapter
from ai_ta_backend.executors.process_pool_executor import \
    ProcessPoolExecutorInterface
from ai_ta_backend.executors.thread_pool_executor import \
    ThreadPoolExecutorAdapter
from ai_ta_backend.executors.thread_pool_executor import \
    ThreadPoolExecutorInterface
from ai_ta_backend.extensions import db
from ai_ta_backend.service.export_service import ExportService
from ai_ta_backend.service.nomic_service import NomicService
from ai_ta_backend.service.posthog_service import PosthogService
from ai_ta_backend.service.retrieval_service import RetrievalService
from ai_ta_backend.service.sentry_service import SentryService
from ai_ta_backend.service.workflow_service import WorkflowService

from ai_ta_backend.redis_queue.ingestQueue import addJobToIngestQueue


app = Flask(__name__)
CORS(app)
executor = Executor(app)
# app.config['EXECUTOR_MAX_WORKERS'] = 5 nothing == picks defaults for me
# app.config['SERVER_TIMEOUT'] = 1000  # seconds

# load API keys from globally-availabe .env file
load_dotenv(override=True)


@app.route('/')
def index() -> Response:
  """_summary_

  Args:
      test (int, optional): _description_. Defaults to 1.

  Returns:
      JSON: _description_
  """
  response = jsonify({"hi there, this is a 404": "Welcome to UIUC.chat backend 🚅 Read the docs here: https://docs.uiuc.chat/ "})
  response.headers.add('Access-Control-Allow-Origin', '*')

  return response


@app.route('/getTopContexts', methods=['POST'])
def getTopContexts(service: RetrievalService) -> Response:
  """Get most relevant contexts for a given search query.
  
  Return value

  ## POST body
  course name (optional) str
      A json response with TBD fields.
  search_query
  token_limit
  doc_groups
  
  Returns
  -------
  JSON
      A json response with TBD fields.
  Metadata fields
  * pagenumber_or_timestamp
  * readable_filename
  * s3_pdf_path
  
  Example: 
  [
    {
      'readable_filename': 'Lumetta_notes', 
      'pagenumber_or_timestamp': 'pg. 19', 
      's3_pdf_path': '/courses/<course>/Lumetta_notes.pdf', 
      'text': 'In FSM, we do this...'
    }, 
  ]

  Raises
  ------
  Exception
      Testing how exceptions are handled.
  """
  data = request.get_json()
  search_query: str = data.get('search_query', '')
  course_name: str = data.get('course_name', '')
  token_limit: int = data.get('token_limit', 3000)
  doc_groups: List[str] = data.get('doc_groups', [])

  logging.info(f"QDRANT URL {os.environ['QDRANT_URL']}")
  logging.info(f"QDRANT_API_KEY {os.environ['QDRANT_API_KEY']}")

  if search_query == '' or course_name == '':
    # proper web error "400 Bad request"
    abort(
        400,
        description=
        f"Missing one or more required parameters: 'search_query' and 'course_name' must be provided. Search query: `{search_query}`, Course name: `{course_name}`"
    )

  found_documents = service.getTopContexts(search_query, course_name, token_limit, doc_groups)

  response = jsonify(found_documents)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/getAll', methods=['GET'])
def getAll(service: RetrievalService) -> Response:
  """Get all course materials based on the course_name
  """
  logging.info("In getAll()")
  course_name: List[str] | str = request.args.get('course_name', default='', type=str)

  if course_name == '':
    # proper web error "400 Bad request"
    abort(400, description=f"Missing the one required parameter: 'course_name' must be provided. Course name: `{course_name}`")

  distinct_dicts = service.getAll(course_name)

  # Convert each Document class instance to a JSON-serializable dict
  json_dicts = [d.to_dict() for d in distinct_dicts]

  response = jsonify({"distinct_files": json_dicts})
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/delete', methods=['DELETE'])
def delete(service: RetrievalService, flaskExecutor: ExecutorInterface):
  """
  Delete a single file from all our database: S3, Qdrant, and Supabase (for now).
  Note, of course, we still have parts of that file in our logs.
  """
  course_name: str = request.args.get('course_name', default='', type=str)
  s3_path: str = request.args.get('s3_path', default='', type=str)
  source_url: str = request.args.get('url', default='', type=str)

  if course_name == '' or (s3_path == '' and source_url == ''):
    # proper web error "400 Bad request"
    abort(
        400,
        description=
        f"Missing one or more required parameters: 'course_name' and ('s3_path' or 'source_url') must be provided. Course name: `{course_name}`, S3 path: `{s3_path}`, source_url: `{source_url}`"
    )

  start_time = time.monotonic()
  # background execution of tasks!!
  flaskExecutor.submit(service.delete_data, course_name, s3_path, source_url)
  logging.info(f"From {course_name}, deleted file: {s3_path}")
  logging.info(f"⏰ Runtime of FULL delete func: {(time.monotonic() - start_time):.2f} seconds")
  # we need instant return. Delets are "best effort" assume always successful... sigh :(
  response = jsonify({"outcome": 'success'})
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


# @app.route('/getNomicMap', methods=['GET'])
# def nomic_map(service: NomicService):
#   course_name: str = request.args.get('course_name', default='', type=str)
#   map_type: str = request.args.get('map_type', default='conversation', type=str)

#   if course_name == '':
#     # proper web error "400 Bad request"
#     abort(400, description=f"Missing required parameter: 'course_name' must be provided. Course name: `{course_name}`")

#   map_id = service.get_nomic_map(course_name, map_type)
#   logging.info("nomic map\n", map_id)

#   response = jsonify(map_id)
#   response.headers.add('Access-Control-Allow-Origin', '*')
#   return response


# @app.route('/createDocumentMap', methods=['GET'])
# def createDocumentMap(service: NomicService):
#   course_name: str = request.args.get('course_name', default='', type=str)

#   if course_name == '':
#     # proper web error "400 Bad request"
#     abort(400, description=f"Missing required parameter: 'course_name' must be provided. Course name: `{course_name}`")

#   map_id = create_document_map(course_name)

#   response = jsonify(map_id)
#   response.headers.add('Access-Control-Allow-Origin', '*')
#   return response


# @app.route('/createConversationMap', methods=['GET'])
# def createConversationMap(service: NomicService):
#   course_name: str = request.args.get('course_name', default='', type=str)

#   if course_name == '':
#     # proper web error "400 Bad request"
#     abort(400, description=f"Missing required parameter: 'course_name' must be provided. Course name: `{course_name}`")

#   map_id = service.create_conversation_map(course_name)

#   response = jsonify(map_id)
#   response.headers.add('Access-Control-Allow-Origin', '*')
#   return response


# @app.route('/logToConversationMap', methods=['GET'])
# def logToConversationMap(service: NomicService, flaskExecutor: ExecutorInterface):
#   course_name: str = request.args.get('course_name', default='', type=str)

#   if course_name == '':
#     # proper web error "400 Bad request"
#     abort(400, description=f"Missing required parameter: 'course_name' must be provided. Course name: `{course_name}`")

#   #map_id = service.log_to_conversation_map(course_name)
#   map_id = flaskExecutor.submit(service.log_to_conversation_map, course_name).result()

#   response = jsonify(map_id)
#   response.headers.add('Access-Control-Allow-Origin', '*')
#   return response


# @app.route('/onResponseCompletion', methods=['POST'])
# def logToNomic(service: NomicService, flaskExecutor: ExecutorInterface):
#   data = request.get_json()
#   course_name = data['course_name']
#   conversation = data['conversation']

#   if course_name == '' or conversation == '':
#     # proper web error "400 Bad request"
#     abort(
#         400,
#         description=
#         f"Missing one or more required parameters: 'course_name' and 'conversation' must be provided. Course name: `{course_name}`, Conversation: `{conversation}`"
#     )
#   logging.info(f"In /onResponseCompletion for course: {course_name}")

#   # background execution of tasks!!
#   #response = flaskExecutor.submit(service.log_convo_to_nomic, course_name, data)
#   flaskExecutor.submit(service.log_to_conversation_map, course_name, conversation).result()
#   response = jsonify({'outcome': 'success'})
#   response.headers.add('Access-Control-Allow-Origin', '*')
#   return response


@app.route('/export-convo-history-csv', methods=['GET'])
def export_convo_history(service: ExportService):
  course_name: str = request.args.get('course_name', default='', type=str)
  from_date: str = request.args.get('from_date', default='', type=str)
  to_date: str = request.args.get('to_date', default='', type=str)

  if course_name == '':
    # proper web error "400 Bad request"
    abort(400, description=f"Missing required parameter: 'course_name' must be provided. Course name: `{course_name}`")

  export_status = service.export_convo_history_json(course_name, from_date, to_date)
  logging.info("EXPORT FILE LINKS: ", export_status)

  if export_status['response'] == "No data found between the given dates.":
    response = Response(status=204)
    response.headers.add('Access-Control-Allow-Origin', '*')

  elif export_status['response'] == "Download from S3":
    response = jsonify({"response": "Download from S3", "s3_path": export_status['s3_path']})
    response.headers.add('Access-Control-Allow-Origin', '*')

  else:
    response = make_response(send_from_directory(export_status['response'][2], export_status['response'][1], as_attachment=True))
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers["Content-Disposition"] = f"attachment; filename={export_status['response'][1]}"
    os.remove(export_status['response'][0])

  return response


@app.route('/export-conversations-custom', methods=['GET'])
def export_conversations_custom(service: ExportService):
  course_name: str = request.args.get('course_name', default='', type=str)
  from_date: str = request.args.get('from_date', default='', type=str)
  to_date: str = request.args.get('to_date', default='', type=str)
  emails: str = request.args.getlist('destination_emails_list')

  if course_name == '' and emails == []:
    # proper web error "400 Bad request"
    abort(400, description="Missing required parameter: 'course_name' and 'destination_email_ids' must be provided.")

  export_status = service.export_conversations(course_name, from_date, to_date, emails)
  logging.info("EXPORT FILE LINKS: ", export_status)

  if export_status['response'] == "No data found between the given dates.":
    response = Response(status=204)
    response.headers.add('Access-Control-Allow-Origin', '*')

  elif export_status['response'] == "Download from S3":
    response = jsonify({"response": "Download from S3", "s3_path": export_status['s3_path']})
    response.headers.add('Access-Control-Allow-Origin', '*')

  else:
    response = make_response(send_from_directory(export_status['response'][2], export_status['response'][1], as_attachment=True))
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers["Content-Disposition"] = f"attachment; filename={export_status['response'][1]}"
    os.remove(export_status['response'][0])

  return response


@app.route('/exportDocuments', methods=['GET'])
def exportDocuments(service: ExportService):
  course_name: str = request.args.get('course_name', default='', type=str)
  from_date: str = request.args.get('from_date', default='', type=str)
  to_date: str = request.args.get('to_date', default='', type=str)

  if course_name == '':
    # proper web error "400 Bad request"
    abort(400, description=f"Missing required parameter: 'course_name' must be provided. Course name: `{course_name}`")

  export_status = service.export_documents_json(course_name, from_date, to_date)
  logging.info("EXPORT FILE LINKS: ", export_status)

  if export_status['response'] == "No data found between the given dates.":
    response = Response(status=204)
    response.headers.add('Access-Control-Allow-Origin', '*')

  elif export_status['response'] == "Download from S3":
    response = jsonify({"response": "Download from S3", "s3_path": export_status['s3_path']})
    response.headers.add('Access-Control-Allow-Origin', '*')

  else:
    response = make_response(send_from_directory(export_status['response'][2], export_status['response'][1], as_attachment=True))
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers["Content-Disposition"] = f"attachment; filename={export_status['response'][1]}"
    os.remove(export_status['response'][0])

  return response


# @app.route('/getTopContextsWithMQR', methods=['GET'])
# def getTopContextsWithMQR(service: RetrievalService, posthog_service: PosthogService) -> Response:
#   """
#   Get relevant contexts for a given search query, using Multi-query retrieval + filtering method.
#   """
#   search_query: str = request.args.get('search_query', default='', type=str)
#   course_name: str = request.args.get('course_name', default='', type=str)
#   token_limit: int = request.args.get('token_limit', default=3000, type=int)
#   if search_query == '' or course_name == '':
#     # proper web error "400 Bad request"
#     abort(
#         400,
#         description=
#         f"Missing one or more required parameters: 'search_query' and 'course_name' must be provided. Search query: `{search_query}`, Course name: `{course_name}`"
#     )

#   posthog_service.capture(event_name='filter_top_contexts_invoked',
#                           properties={
#                               'user_query': search_query,
#                               'course_name': course_name,
#                               'token_limit': token_limit,
#                           })

#   found_documents = service.getTopContextsWithMQR(search_query, course_name, token_limit)

#   response = jsonify(found_documents)
#   response.headers.add('Access-Control-Allow-Origin', '*')
#   return response


@app.route('/getworkflows', methods=['GET'])
def get_all_workflows(service: WorkflowService) -> Response:
  """
  Get all workflows from user.
  """

  api_key = request.args.get('api_key', default='', type=str)
  limit = request.args.get('limit', default=100, type=int)
  pagination = request.args.get('pagination', default=True, type=bool)
  active = request.args.get('active', default=False, type=bool)
  name = request.args.get('workflow_name', default='', type=str)
  logging.info(request.args)

  logging.info("In get_all_workflows.. api_key: ", api_key)

  # if no API Key, return empty set.
  # if api_key == '':
  #   # proper web error "400 Bad request"
  #   abort(400, description=f"Missing N8N API_KEY: 'api_key' must be provided. Search query: `{api_key}`")

  try:
    response = service.get_workflows(limit, pagination, api_key, active, name)
    response = jsonify(response)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response
  except Exception as e:
    if "unauthorized" in str(e).lower():
      logging.info("Unauthorized error in get_all_workflows: ", e)
      abort(401, description=f"Unauthorized: 'api_key' is invalid. Search query: `{api_key}`")
    else:
      logging.info("Error in get_all_workflows: ", e)
      abort(500, description=f"Failed to fetch n8n workflows: {e}")


@app.route('/switch_workflow', methods=['GET'])
def switch_workflow(service: WorkflowService) -> Response:
  """
  Activate or deactivate flow for user.
  """

  api_key = request.args.get('api_key', default='', type=str)
  activate = request.args.get('activate', default='', type=str)
  id = request.args.get('id', default='', type=str)

  logging.info(request.args)

  if api_key == '':
    # proper web error "400 Bad request"
    abort(400, description=f"Missing N8N API_KEY: 'api_key' must be provided. Search query: `{api_key}`")

  try:
    logging.info("activation!!!!!!!!!!!", activate)
    response = service.switch_workflow(id, api_key, activate)
    response = jsonify(response)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response
  except Exception as e:
    if e == "Unauthorized":
      abort(401, description=f"Unauthorized: 'api_key' is invalid. Search query: `{api_key}`")
    else:
      abort(400, description=f"Bad request: {e}")


@app.route('/run_flow', methods=['POST'])
def run_flow(service: WorkflowService) -> Response:
  """
  Run flow for a user and return results.
  """

  api_key = request.json.get('api_key', '')
  name = request.json.get('name', '')
  data = request.json.get('data', '')

  logging.info("Got /run_flow request:", request.json)

  if api_key == '':
    # proper web error "400 Bad request"
    abort(400, description=f"Missing N8N API_KEY: 'api_key' must be provided. Search query: `{api_key}`")

  try:
    response = service.main_flow(name, api_key, data)
    response = jsonify(response)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response
  except Exception as e:
    if e == "Unauthorized":
      abort(401, description=f"Unauthorized: 'api_key' is invalid. Search query: `{api_key}`")
    else:
      abort(400, description=f"Bad request: {e}")

@app.route('/ingest', methods=['POST'])
def ingest() -> Response:
  logging.info("In /ingest")

  data = request.get_json()
  logging.info("Data received: %s", data)
  # send data to redis_queue/ingestQueue.py
  result = addJobToIngestQueue(data)
  logging.info("Result from addJobToIngestQueue:  %s", result)

  response = jsonify(
    {
      "outcome": f'Queued Ingest task',
      "ingest_task_id": result
    }
  )
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


def configure(binder: Binder) -> None:
  vector_bound = False
  sql_bound = False
  storage_bound = False

  # Encode the PostgreSQL password
  #encoded_password = quote_plus(os.getenv('POSTGRES_PASSWORD'))
  #print("ENCODED PASSWORD (i.e., POSTGRES_PASSWORD):", encoded_password)

  # Define database URLs with corrected environment variables
  # DB_URLS = {
  #     'supabase':
  #         f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}",
  #     'sqlite':
  #         f"sqlite:///{os.getenv('SQLITE_DB_NAME')}" if os.getenv('SQLITE_DB_NAME') else None,
  #     'postgres':
  #         f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
  #         if all([
  #             os.getenv('POSTGRES_USER'),
  #             os.getenv('POSTGRES_PASSWORD'),
  #             os.getenv('POSTGRES_HOST'),
  #             os.getenv('POSTGRES_PORT'),
  #             os.getenv('POSTGRES_DB')
  #         ]) else None
  # }
  # print("DB_URLS:", DB_URLS)

  # # Bind to the first available SQL database configuration
  # for db_type, url in DB_URLS.items():
  #   if url:
  #     logging.info(f"Binding to {db_type} database with URL: {url}")
  #     with app.app_context():
  #       app.config['SQLALCHEMY_DATABASE_URI'] = url
  #       db.init_app(app)

  #       # Check if tables exist before creating them
  #       inspector = inspect(db.engine)
  #       existing_tables = inspector.get_table_names()
  #       print("Existing tables:", existing_tables)
  #       if not existing_tables:
  #         logging.info("Creating tables as the database is empty")
  #         db.create_all()
  #       else:
  #         logging.info("Tables already exist, skipping creation")

  #     binder.bind(SQLAlchemyDatabase, to=SQLAlchemyDatabase(db), scope=SingletonScope)
  #     sql_bound = True
  #     break
  DB_URLS = {
      'supabase':
          f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}",
  }
  # Try to connect to Supabase and verify connection
  for db_type, url in DB_URLS.items():
    if url:
      logging.info(f"Attempting to connect to {db_type} database with URL: {url}")
      try:
        with app.app_context():
          app.config['SQLALCHEMY_DATABASE_URI'] = url
          db.init_app(app)
          
          # Test connection by executing a simple query with text()
          with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            connection.commit()  # Add commit to ensure transaction completion
            logging.info(f"✅ Successfully connected to {db_type} database")
          
          # Check if tables exist
          inspector = inspect(db.engine)
          existing_tables = inspector.get_table_names()
          logging.info(f"Found existing tables: {existing_tables}")
          
          if not existing_tables:
            logging.info("Creating tables as database is empty")
            db.create_all()
          
        binder.bind(SQLAlchemyDatabase, to=SQLAlchemyDatabase(db), scope=SingletonScope)
        sql_bound = True
        break
        
      except Exception as e:
        logging.error(f"❌ Failed to connect to {db_type} database: {str(e)}")
        continue

  # Conditionally bind databases based on the availability of their respective secrets
  if all(os.getenv(key) for key in ["QDRANT_URL", "QDRANT_COLLECTION_NAME"]) or any(
      os.getenv(key) for key in ["PINECONE_API_KEY", "PINECONE_PROJECT_NAME"]):
    logging.info("Binding to Qdrant database")

    logging.info(f"Qdrant Collection Name: {os.environ['QDRANT_COLLECTION_NAME']}")
    logging.info(f"Qdrant URL: {os.environ['QDRANT_URL']}")
    if os.getenv("QDRANT_API_KEY"):
      logging.info(f"Qdrant API Key: {os.environ['QDRANT_API_KEY']}")
    else:
      logging.warning("Qdrant API Key is not set")
    binder.bind(VectorDatabase, to=VectorDatabase, scope=SingletonScope)
    vector_bound = True

  if any(os.getenv(key) for key in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "S3_BUCKET_NAME", "MINIO_URL"]):
    if os.getenv("MINIO_URL"):
      logging.info("Binding to MinIO storage")
    else:
      logging.info("Binding to AWS S3 storage")
    binder.bind(AWSStorage, to=AWSStorage, scope=SingletonScope)
    storage_bound = True

  # Conditionally bind services based on the availability of their respective secrets
  if os.getenv("NOMIC_API_KEY"):
    logging.info("Binding to Nomic service")
    binder.bind(NomicService, to=NomicService, scope=SingletonScope)

  if os.getenv("POSTHOG_API_KEY"):
    logging.info("Binding to Posthog service")
    binder.bind(PosthogService, to=PosthogService, scope=SingletonScope)

  if os.getenv("SENTRY_DSN"):
    logging.info("Binding to Sentry service")
    binder.bind(SentryService, to=SentryService, scope=SingletonScope)

  if os.getenv("EMAIL_SENDER"):
    logging.info("Binding to Export service")
    binder.bind(ExportService, to=ExportService, scope=SingletonScope)

  if os.getenv("N8N_URL"):
    logging.info("Binding to Workflow service")
    binder.bind(WorkflowService, to=WorkflowService, scope=SingletonScope)

  if vector_bound and sql_bound and storage_bound:
    logging.info("Binding to Retrieval service")
    binder.bind(RetrievalService, to=RetrievalService, scope=RequestScope)

  # Always bind the executor and its adapters
  binder.bind(ExecutorInterface, to=FlaskExecutorAdapter(executor), scope=SingletonScope)
  binder.bind(ThreadPoolExecutorInterface, to=ThreadPoolExecutorAdapter, scope=SingletonScope)
  binder.bind(ProcessPoolExecutorInterface, to=ProcessPoolExecutorAdapter, scope=SingletonScope)
  logging.info("Configured all services and adapters", binder._bindings)

  # TODO: Initialize the databases 

  # Qdrant
  # Initialize Qdrant collection if it doesn't exist
  try:
    qdrant_client = QdrantClient(
        url=os.getenv('QDRANT_URL', 'http://qdrant:6333'),
        https=False,
        api_key=os.getenv('QDRANT_API_KEY'),
        timeout=20,
    )
    
    # Create collection with OpenAI embedding dimensions
    qdrant_client.recreate_collection(
        collection_name=os.environ['QDRANT_COLLECTION_NAME'],
        vectors_config=models.VectorParams(
            size=1536,  # OpenAI embedding dimensions
            distance=models.Distance.COSINE
        )
    )
    logging.info(f"Initialized Qdrant collection: {os.environ['QDRANT_COLLECTION_NAME']}")
  except Exception as e:
    logging.error(f"Failed to initialize Qdrant collection: {str(e)}")

  # Initialize Minio
  try:
    s3_client = boto3.client(
        's3',
        endpoint_url=os.getenv('MINIO_URL'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    )

    # Create bucket if it doesn't exist
    bucket_name = os.environ['S3_BUCKET_NAME']
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        logging.info(f"S3 bucket already exists: {bucket_name}")

        # Create courses/ path by putting an empty object
        s3_client.put_object(
            Bucket=bucket_name,
            Key='courses/'
        )
        logging.info(f"Created courses/ path in bucket: {bucket_name}")
    except:
        s3_client.create_bucket(Bucket=bucket_name)
        logging.info(f"Created S3 bucket: {bucket_name}")
        
        # Create courses/ path in new bucket
        s3_client.put_object(
            Bucket=bucket_name,
            Key='courses/'
        )
        logging.info(f"Created courses/ path in bucket: {bucket_name}")
  except Exception as e:
    logging.error(f"Failed to initialize S3 bucket: {str(e)}")


FlaskInjector(app=app, modules=[configure])

if __name__ == '__main__':
  app.run(debug=True, port=int(os.getenv("PORT", default=8000)))  # nosec -- reasonable bandit error suppression