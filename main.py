import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from qdrant_client import QdrantClient

app = Flask(__name__)
CORS(app)

# load API keys from globally-availabe .env file
load_dotenv(dotenv_path='.env', override=True)

@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})

@app.route('/getContexts', methods=['GET'])
def getContexts():
    """_summary_

    :raises Exception: This is an error message!
    :return: _description_
    :rtype: _type_
    """
    language: str = request.args.get('language')
    response:str = jsonify({"language": f"You said: {language}"})
    response.headers.add('Access-Control-Allow-Origin', '*')
    if language == 'error':
        raise Exception('This is an error message!')
    return response

@app.route('/sayhi', methods=['GET'])
def sayhi():
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
