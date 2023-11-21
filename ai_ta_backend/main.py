import gc
import json
import os
import time
from typing import List

from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, request, send_file, make_response, send_from_directory
from flask_cors import CORS
from flask_executor import Executor
from sqlalchemy import JSON

from ai_ta_backend.canvas import CanvasAPI
from ai_ta_backend.nomic_logging import get_nomic_map, log_convo_to_nomic
from ai_ta_backend.vector_database import Ingest
from ai_ta_backend.web_scrape import WebScrape, mit_course_download
from ai_ta_backend.canvas import CanvasAPI
from ai_ta_backend.export_data import export_convo_history_csv

app = Flask(__name__)
CORS(app)
executor = Executor(app)
# app.config['EXECUTOR_MAX_WORKERS'] = 5 nothing == picks defaults for me

# load API keys from globally-availabe .env file
load_dotenv()

@app.route('/')
def index() -> Response:
  """_summary_

  Args:
      test (int, optional): _description_. Defaults to 1.

  Returns:
      JSON: _description_
  """
  response = jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/coursera', methods=['GET'])
def coursera() -> Response:
  try:
    course_name: str = request.args.get('course_name')  # type: ignore
    coursera_course_name: str = request.args.get('coursera_course_name')  # type: ignore
  except Exception as e:
    print(f"No course name provided: {e}")

  ingester = Ingest()
  results = ingester.ingest_coursera(coursera_course_name, course_name)  # type: ignore
  del ingester

  response = jsonify(results)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/github', methods=['GET'])
def github() -> Response:
  course_name: str = request.args.get('course_name', default='', type=str)
  github_url: str = request.args.get('github_url', default='', type=str)

  if course_name == '' or github_url == '':
    # proper web error "400 Bad request"
    abort(
        400,
        description=
        f"Missing one or more required parameters: 'course_name' and 's3_path' must be provided. Course name: `{course_name}`, S3 path: `{github_url}`"
    )


  ingester = Ingest()
  results = ingester.ingest_github(github_url, course_name)
  del ingester
  response = jsonify(results)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/delete-entire-course', methods=['GET'])
def delete_entire_course() -> Response:
  try:
    course_name: str = request.args.get('course_name')  # type: ignore
    # coursera_course_name: str = request.args.get('coursera_course_name') # type: ignore
  except Exception as e:
    print(f"No course name provided: {e}")

  ingester = Ingest()
  results = ingester.delete_entire_course(course_name)  # type: ignore
  del ingester

  response = jsonify(results)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/getTopContexts', methods=['GET'])
def getTopContexts() -> Response:
  """Get most relevant contexts for a given search query.
  
  Return value

  ## GET arguments
  course name (optional) str
      A json response with TBD fields.
  search_query
  top_n
  
  Returns
  -------
  JSON
      A json response with TBD fields.
  Metadata fileds
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
  print("In getRopContexts in Main()")
  search_query: str = request.args.get('search_query', default='', type=str)
  course_name: str = request.args.get('course_name', default='', type=str)
  token_limit: int = request.args.get('token_limit', default=3000, type=int)
  if search_query == '' or course_name == '':
    # proper web error "400 Bad request"
    abort(
        400,
        description=
        f"Missing one or more required parameters: 'search_query' and 'course_name' must be provided. Search query: `{search_query}`, Course name: `{course_name}`"
    )

  ingester = Ingest()
  found_documents = ingester.getTopContexts(search_query, course_name, token_limit)
  del ingester

  response = jsonify(found_documents)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response



@app.route('/get_stuffed_prompt', methods=['GET'])
def get_stuffed_prompt() -> Response:
  """Get most relevant contexts for a given search query.
  
  ## GET arguments
  course name (optional) str
      A json response with TBD fields.
  search_query
  top_n
  
  Returns
  -------
    String
    
  """
  course_name: str = request.args.get('course_name', default='', type=str)
  search_query: str = request.args.get('search_query', default='', type=str)
  token_limit: int = request.args.get('token_limit', default=-1, type=int)
  if course_name == '' or search_query == '' or token_limit == -1:
    # proper web error "400 Bad request"
    abort(
        400,
        description=
        f"Missing one or more required parameters: 'course_name', 'search_query', and 'token_limit' must be provided. Course name: `{course_name}`, Search query: `{search_query}`, Token limit: `{token_limit}`"
    )

  print("In /getTopContexts: ", search_query)
  if search_query is None:
    return jsonify({"error": "No parameter `search_query` provided. It is undefined."})
  if token_limit is None:
    token_limit = 3_000
  else:
    token_limit = int(token_limit)

  ingester = Ingest()
  prompt = ingester.get_stuffed_prompt(search_query, course_name, token_limit)
  del ingester

  response = jsonify(prompt)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/ingest', methods=['GET'])
def ingest() -> Response:
  """Recursively ingests anything from S3 filepath and below. 
  Pass a s3_paths filepath (not URL) into our S3 bucket.
  
  Ingests all files, not just PDFs. 
  
  args:
    s3_paths: str | List[str]

  Returns:
      str: Success or Failure message. Failure message if any failures. TODO: email on failure.
  """
  s3_paths: List[str] | str = request.args.get('s3_paths', default='')
  readable_filename: List[str] | str = request.args.get('readable_filename', default='')
  course_name: List[str] | str = request.args.get('course_name', default='')
  print(f"In top of /ingest route. course: {course_name}, s3paths: {s3_paths}")

  if course_name == '' or s3_paths == '':
    # proper web error "400 Bad request"
    abort(
        400,
        description=
        f"Missing one or more required parameters: 'course_name' and 's3_path' must be provided. Course name: `{course_name}`, S3 path: `{s3_paths}`"
    )

  ingester = Ingest()
  if readable_filename == '':
    success_fail_dict = ingester.bulk_ingest(s3_paths, course_name)
  else:
    success_fail_dict = ingester.bulk_ingest(s3_paths, course_name, readable_filename=readable_filename)
  print(f"Bottom of /ingest route. success or fail dict: {success_fail_dict}")
  del ingester

  response = jsonify(success_fail_dict)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/getContextStuffedPrompt', methods=['GET'])
def getContextStuffedPrompt() -> Response:
  """
  Get a stuffed prompt for a given user question and course name.
  Args : 
    search_query (str)
    course_name (str) : used for metadata filtering
  Returns : str
    a very long "stuffed prompt" with question + summaries of 20 most relevant documents.
  """
  print("In /getContextStuffedPrompt")

  ingester = Ingest()
  search_query: str = request.args.get('search_query', default='', type=str)
  course_name: str = request.args.get('course_name', default='', type=str)
  top_n: int = request.args.get('top_n', default=-1, type=int)
  top_k_to_search: int = request.args.get('top_k_to_search', default=-1, type=int)
  
  if search_query == '' or course_name == '' or top_n == -1 or top_k_to_search == -1:
    # proper web error "400 Bad request"
    abort(
        400,
        description=
        f"Missing one or more required parameters: 'search_query', 'course_name', 'top_n', and 'top_k_to_search' must be provided. Search query: `{search_query}`, Course name: `{course_name}`, Top N: `{top_n}`, Top K to search: `{top_k_to_search}`"
    )

  start_time = time.monotonic()
  stuffed_prompt = ingester.get_context_stuffed_prompt(search_query, course_name, top_n, top_k_to_search)
  print(f"⏰ Runtime of EXTREME prompt stuffing: {(time.monotonic() - start_time):.2f} seconds")
  del ingester

  response = jsonify({"prompt": stuffed_prompt})
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/getAll', methods=['GET'])
def getAll() -> Response:
  """Get all course materials based on the course_name
  """
  course_name: List[str] | str = request.args.get('course_name', default='', type=str)

  if course_name == '':
    # proper web error "400 Bad request"
    abort(
        400,
        description=
        f"Missing the one required parameter: 'course_name' must be provided. Course name: `{course_name}`"
    )

  ingester = Ingest()
  distinct_dicts = ingester.getAll(course_name)
  del ingester

  response = jsonify({"distinct_files": distinct_dicts})
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/delete', methods=['DELETE'])
def delete():
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
  ingester = Ingest()
  # background execution of tasks!! 
  executor.submit(ingester.delete_data, course_name, s3_path, source_url)
  print(f"From {course_name}, deleted file: {s3_path}")
  print(f"⏰ Runtime of FULL delete func: {(time.monotonic() - start_time):.2f} seconds")
  del ingester

  # we need instant return. Delets are "best effort" assume always successful... sigh :(
  response = jsonify({"outcome": 'success'})
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response

@app.route('/web-scrape', methods=['GET'])
def scrape() -> Response:
  url: str = request.args.get('url', default='', type=str)
  course_name: str = request.args.get('course_name', default='', type=str)
  max_urls: int = request.args.get('max_urls', default=100, type=int)
  max_depth: int = request.args.get('max_depth', default=2, type=int)
  timeout: int = request.args.get('timeout', default=3, type=int)
  # stay_on_baseurl = request.args.get('stay_on_baseurl', default='', type=str)
  stay_on_baseurl: bool = request.args.get('stay_on_baseurl', default=True, type=lambda x: x.lower() == 'true')
  depth_or_breadth:str = request.args.get('depth_or_breadth', default='breadth', type=str)

  if url == '' or max_urls == -1 or max_depth == -1 or timeout == -1 or course_name == '' or stay_on_baseurl is None:
    # proper web error "400 Bad request"
    abort(
        400,
        description=
        f"Missing one or more required parameters: 'url', 'max_urls', 'max_depth', 'timeout', 'course_name', and 'stay_on_baseurl' must be provided. url: `{url}`, max_urls: `{max_urls}`, max_depth: `{max_depth}`, timeout: `{timeout}`, course_name: `{course_name}`, stay_on_baseurl: `{stay_on_baseurl}`"
    )

  # print all input params
  print(f"Web scrape: {url}")
  print(f"Max Urls: {max_urls}")
  print(f"Max Depth: {max_depth}")
  print(f"Stay on BaseURL: {stay_on_baseurl}")
  print(f"Timeout in Seconds ⏰: {timeout}")
  
  scraper = WebScrape()
  success_fail_dict = scraper.main_crawler(url, course_name, max_urls, max_depth, timeout, stay_on_baseurl, depth_or_breadth)

  response = jsonify(success_fail_dict)
  response.headers.add('Access-Control-Allow-Origin', '*')
  gc.collect() # manually invoke garbage collection, try to reduce memory on Railway $$$
  return response

@app.route('/mit-download', methods=['GET'])
def mit_download_course() -> Response:
  """ Web scraper built for 
  """
  url: str = request.args.get('url', default='', type=str)
  course_name: str = request.args.get('course_name', default='', type=str)
  local_dir: str = request.args.get('local_dir', default='', type=str)

  if url == '' or course_name == '' or local_dir == '':
    # proper web error "400 Bad request"
    abort(
        400,
        description=
        f"Missing one or more required parameters: 'url', 'course_name', and 'local_dir' must be provided. url: `{url}`, course_name: `{course_name}`, local_dir: `{local_dir}`"
    )

  success_fail = mit_course_download(url, course_name, local_dir)

  response = jsonify(success_fail)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response

@app.route('/addCanvasUsers', methods=['GET'])
def add_canvas_users():
  """
  Add users from canvas to the course
  """
  print("In /addCanvasUsers")

  canvas = CanvasAPI()
  canvas_course_id: str = request.args.get('course_id')
  course_name: str = request.args.get('course_name')

  success_or_failure = canvas.add_users(canvas_course_id, course_name)
  
  response = jsonify({"outcome": success_or_failure})

  response.headers.add('Access-Control-Allow-Origin', '*')
  return response

@app.route('/ingestCanvas', methods=['GET'])
def ingest_canvas():
  """
  Ingest course content from Canvas
  """
  print("made it to ingest")
  canvas = CanvasAPI()
  canvas_course_id: str = request.args.get('course_id')
  course_name: str = request.args.get('course_name')

  # Retrieve the checkbox values from the request and create the content_ingest_dict
  # Set default values to True if not provided in the request
  content_ingest_dict = {
      'files': request.args.get('files', 'true').lower() == 'true',
      'pages': request.args.get('pages', 'true').lower() == 'true',
      'modules': request.args.get('modules', 'true').lower() == 'true',
      'syllabus': request.args.get('syllabus', 'true').lower() == 'true',
      'assignments': request.args.get('assignments', 'true').lower() == 'true',
      'discussions': request.args.get('discussions', 'true').lower() == 'true'
  }

  if canvas_course_id == '' or course_name == '':
    # proper web error "400 Bad request"
    abort(
        400,
        description=
        f"Missing one or more required parameters: 'course_id' and 'course_name' must be provided. course_id: `{canvas_course_id}`, course_name: `{course_name}`"
    )

  success_or_failure = canvas.ingest_course_content(canvas_course_id, course_name, content_ingest_dict)
  response = jsonify({"outcome": success_or_failure})
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response

@app.route('/getNomicMap', methods=['GET'])
def nomic_map():
  course_name: str = request.args.get('course_name', default='', type=str)
  if course_name == '':
    # proper web error "400 Bad request"
    abort(
        400,
        description=
        f"Missing required parameter: 'course_name' must be provided. Course name: `{course_name}`"
    )

  map_id = get_nomic_map(course_name)
  print("nomic map\n", map_id)

  response = jsonify(map_id)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response

@app.route('/onResponseCompletion', methods=['POST'])
def logToNomic():
  data = request.get_json()
  course_name = data['course_name']
  conversation = data['conversation']
  if course_name == '' or conversation == '':
    # proper web error "400 Bad request"
    abort(
        400,
        description=
        f"Missing one or more required parameters: 'course_name' and 'conversation' must be provided. Course name: `{course_name}`, Conversation: `{conversation}`"
    )
  print(f"In /onResponseCompletion for course: {course_name}")

  # background execution of tasks!! 
  response = executor.submit(log_convo_to_nomic, course_name, data)
  response = jsonify({'outcome': 'success'})
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response

@app.route('/export-convo-history-csv', methods=['GET'])
def export_convo_history():
  course_name: str = request.args.get('course_name', default='', type=str)
  from_date: str = request.args.get('from_date', default='', type=str)
  to_date: str = request.args.get('to_date', default='', type=str)

  if course_name == '':
    # proper web error "400 Bad request"
    abort(
        400,
        description=
        f"Missing required parameter: 'course_name' must be provided. Course name: `{course_name}`"
    )

  export_status = export_convo_history_csv(course_name, from_date, to_date)
  print("EXPORT FILE LINKS: ",  export_status)
  
  response = make_response(send_from_directory(export_status[2], export_status[1], as_attachment=True))
  response.headers.add('Access-Control-Allow-Origin', '*')
  response.headers["Content-Disposition"] = f"attachment; filename={export_status[1]}"
  
  os.remove(export_status[0])
  return response


if __name__ == '__main__':
  app.run(debug=True, port=int(os.getenv("PORT", default=8000)))
