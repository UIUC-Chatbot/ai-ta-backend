import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from qdrant_client import QdrantClient
from sqlalchemy import JSON

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
    course_name: str = request.args.get('course_name')
  except Exception as e:
    print("No course name provided.")

  course_name: str = request.args.get('course_name')
  
  ret = {'course_name': course_name, 'contexts': [{'source_name': 'Lumetta_notes', 'source_location': 'pg. 19', 'text': 'In FSM, we do this...'}, {'source_name': 'Lumetta_notes', 'source_location': 'pg. 20', 'text': 'In Assembly language, the code does that...'},]}
  
  response:str = jsonify(ret)
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


def get_contexts():
  contexts = {'language': 'python', 'framework': 'Flask'}
  response = jsonify(contexts)
  return response



@app.route('/getqdrant')
def getqdrant():
  qdrant_client = QdrantClient(
      url=os.environ.get("QDRANT_URL"),
      api_key=os.environ.get("QDRANT_API_KEY"),
  )
  return 'Placeholder return'


if __name__ == '__main__':
  app.run(debug=True, port=os.getenv("PORT", default=5000))
