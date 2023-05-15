import os

from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})

@app.route('/getContexts')
def getContexts():
    language = request.args.get('language')
    return jsonify({"language": f"You said: {language}"})



if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
