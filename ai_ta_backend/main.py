import os
import re
import time
from typing import Any, List

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
# from qdrant_client import QdrantClient
from sqlalchemy import JSON

from ai_ta_backend.vector_database import Ingest

app = Flask(__name__)
CORS(app)

# load API keys from globally-availabe .env file
# load_dotenv(dotenv_path='.env', override=True)
load_dotenv()

@app.route('/')
def index() -> JSON:
  """_summary_

  Args:
      test (int, optional): _description_. Defaults to 1.

  Returns:
      JSON: _description_
  """
  return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})


@app.route('/coursera', methods=['GET'])
def coursera() -> JSON:
  try:
    course_name: str = request.args.get('course_name') # type: ignore
    coursera_course_name: str = request.args.get('coursera_course_name') # type: ignore
  except Exception as e:
    print(f"No course name provided: {e}")
  
  ingester = Ingest()
  results = ingester.ingest_coursera(coursera_course_name, course_name) # type: ignore
  response = jsonify(results)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/getTopContexts', methods=['GET'])
def getTopContexts():
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
  # todo: best way to handle optional arguments?
  try:
    course_name: str = request.args.get('course_name')
    search_query: str = request.args.get('search_query')
    top_n: str = request.args.get('top_n')
  except Exception as e:
    print("No course name provided.")

  print("In /getTopContexts: ", search_query)
  if search_query is None:
    return jsonify({"error": "No parameter `search_query` provided. It is undefined."})

  ingester = Ingest()
  found_documents = ingester.getTopContexts(search_query, course_name, top_n)

  response = jsonify(found_documents)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/ingest', methods=['GET'])
def ingest():
  """Recursively ingests anything from S3 filepath and below. 
  Pass a s3_paths filepath (not URL) into our S3 bucket.
  
  Ingests all files, not just PDFs. 
  
  args:
    s3_paths: str | List[str]

  Returns:
      str: Success or Failure message. Failure message if any failures. TODO: email on failure.
  """

  print("In /ingest")

  ingester = Ingest()
  s3_paths: List[str] | str = request.args.get('s3_paths')
  course_name: List[str] | str = request.args.get('course_name')
  success_fail_dict = ingester.bulk_ingest(s3_paths, course_name)

  response = jsonify(success_fail_dict)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/getContextStuffedPrompt', methods=['GET'])
def getContextStuffedPrompt():
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
  user_question: str = str(request.args.get('search_query'))      # type: ignore
  course_name: str = str(request.args.get('course_name'))         # type: ignore 
  top_n: int = int(request.args.get('top_n'))                     # type: ignore
  top_k_to_search: int = int(request.args.get('top_k_to_search')) # type: ignore

  start_time = time.monotonic()
  stuffed_prompt = ingester.get_context_stuffed_prompt(search_query, course_name, top_n, top_k_to_search)
  print(f"⏰ Runtime of EXTREME prompt stuffing: {(time.monotonic() - start_time):.2f} seconds")
  response = jsonify({"prompt": stuffed_prompt})

  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/getAll', methods=['GET'])
def getAll():
  """Get all course materials based on the course_name
  """

  print("In /getAll")

  ingester = Ingest()
  course_name: List[str] | str = request.args.get('course_name')
  distinct_dicts = ingester.getAll(course_name)
  response = jsonify({"all_s3_paths": distinct_dicts})

  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


#Write api to delete s3 files for a course
@app.route('/delete', methods=['DELETE'])
def delete():
    """Delete all course materials based on the course_name
    """

    print("In /delete")

    ingester = Ingest()
    course_name: List[str] | str = request.args.get('course_name')
    s3_path: str = request.args.get('s3_path')
    success_or_failure = ingester.delete_data(s3_path, course_name)
    response = jsonify({"outcome": success_or_failure})

    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


@app.route('/log', methods=['GET'])
def log():
  """
  todo
  """

  print("In /log")

  ingester = Ingest()
  # course_name: List[str] | str = request.args.get('course_name')
  success_or_failure = ingester.log_to_arize('course_name', 'test', 'completion')
  response = jsonify({"outcome": success_or_failure})

  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


if __name__ == '__main__':
  app.run(debug=True, port=os.getenv("PORT", default=8000))
