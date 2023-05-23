import os
from typing import Any, List

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
# from qdrant_client import QdrantClient
from sqlalchemy import JSON
from VectorDatabase import Ingest

app = Flask(__name__)
CORS(app)

# load API keys from globally-availabe .env file
load_dotenv(dotenv_path='../.env', override=True)

@app.route('/')
def index()->JSON:
  """_summary_

  Args:
      test (int, optional): _description_. Defaults to 1.

  Returns:
      JSON: _description_
  """
  return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})

@app.route('/getTopContexts', methods=['GET'])
def getContexts():
  """Here's a summary of the work.

  ## GET arguments
  course name (optional) str
      A json response with TBD fields.
      
  Returns
  -------
  JSON
      A json response with TBD fields.

  Raises
  ------
  Exception
      Testing how exceptions are handled.
  """
  # todo: best way to handle optional arguments?
  try:
    course_name: str = request.args.get('course_name')
    if course_name == 'error':
      raise Exception(f'The course name `{course_name}` was invalid!')
  except Exception as e:
    print(f"No valid course name provided. Error: {e}")
  try:
    search_query: str = request.args.get('search_query')
  except Exception as e:
    print("No course name provided.")

  
  ingester = Ingest()
  found_documents = ingester.getTopContexts(search_query)
  
  # ret = {'course_name': course_name, 'contexts': [{'source_name': 'Lumetta_notes', 'source_location': 'pg. 19', 'text': 'In FSM, we do this...'}, {'source_name': 'Lumetta_notes', 'source_location': 'pg. 20', 'text': 'In Assembly language, the code does that...'},]}
  
  # TypeError: Object of type Document is not JSON serializable
  response:str = jsonify(found_documents)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response

@app.route('/sayhi', methods=['GET'])
def sayhi( ):
  """Here's what it does
  
  Parameters
  ----------
  cool : str, optional 

  Returns
  -------
  JSON
      A simple json response.
  
  Example usage
  -------------
  First mode, *buffer* is `None`:
  ```python
  sayhi(cool='cool')
  {"language": "Hi there: cool"}
  ```
  """
  language = request.args.get('language')
  response = jsonify({"language": f"Hi there: {language}"})
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response

@app.route('/S3_dir_ingest', methods=['GET'])
def S3_dir_ingest( ):
  """Rough ingest of whole S3 dir. Pretty handy.
  
  S3 path, NO BUCKET. We assume the bucket is an .env variable.

  Returns:
      str: Success or Failure message
  """
  
  ingester = Ingest()
  
  s3_path: List[str] | str = request.args.get('s3_path')
  # course_name: List[str] | str = request.args.get('course_name')
  ret = ingester.ingest_S3_directory(s3_path)
  if ret == 'success':
    response = jsonify({"ingest_status": "success"})
  else:
    response = jsonify({"ingest_status": ret})
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response



@app.route('/ingest', methods=['GET'])
def ingest( ):
  """Ingests PDFs from S3 filepath (not RUL) into our internal systems.
  
  TODO: change to ingest all files, not just PDFs. 
  
  args:
    s3_paths: str | List[str]

  Returns:
      _type_: _description_
  """
  
  ingester = Ingest()
  
  s3_paths: List[str] | str = request.args.get('s3_paths')
  course_name: List[str] | str = request.args.get('course_name')
  ret = ingester.bulk_ingest(s3_paths, course_name)
  if ret == 'success':
    response = jsonify({"ingest_status": "success"})
  else:
    response = jsonify({"ingest_status": ret})
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response

@app.route('/sayhifromrohan', methods=['GET'])
def sayhifromrohan( ):
  """Here's what it does

  Parameters
  ----------
  cool : str, optional

  Returns
  -------
  JSON
      A simple json response.

  Example usage
  -------------
  First mode, *buffer* is `None`:
  ```python
  sayhi(cool='cool')
  {"language": "Hi there: cool"}
  ```
  """
  language = request.args.get('language')
  response = jsonify({"language": f"Hi there: {language}"})
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response

@app.route('/test_endpoint', methods=['GET'])
def test_endpoint( ):
  """Here's what it does
  
  Parameters
  ----------
  cool : str, optional 

  Returns
  -------
  JSON
      A simple json response.
  
  Example usage
  -------------
  First mode, *buffer* is `None`:
  ```python
  sayhi(cool='cool')
  {"language": "Hi there: cool"}
  ```
  """
  language = request.args.get('language')
  response = jsonify({"language": f"This is a test endpoint: {language}"})
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response

@app.route('/test_endpoint2', methods=['GET'])
def neha_sayhi( ):
  """Here's what it does
  
  Parameters
  ----------
  cool : str, optional 

  Returns
  -------
  JSON
      A simple json response.
  
  Example usage
  -------------
  First mode, *buffer* is `None`:
  ```python
  sayhi(cool='cool')
  {"language": "Hi there: cool"}
  ```
  """
  language = request.args.get('language')
  response = jsonify({"language": f"Hi there: {language}"})
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response




def get_contexts():
  contexts = {'language': 'python', 'framework': 'Flask'}
  response = jsonify(contexts)
  return response




if __name__ == '__main__':
  app.run(debug=True, port=os.getenv("PORT", default=5000))
