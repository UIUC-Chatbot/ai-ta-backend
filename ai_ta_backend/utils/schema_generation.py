import json
from ollama import Client

OLLAMA_CLIENT = Client(host="https://secret-ollama.ncsa.ai")
LLM = 'llama3.1:70b'

def generate_schema_from_project_description(project_name: str, project_description: str) -> dict:
    """
    Generate metadata schema using project_name and project_description
    """

    if not project_description:
        # return default schema
        project_schema = {
            "document_type": {
                "type": "string",
            },
            "document_title": {
                "type": "string",
            },
            "author": {
                "type": "string",
            },
            "creation_date": {
                "type": "string",
                "format": "date",
            },
            "keywords": {
                "type": "array",
                "items": {
                    "type": "string"
                }
            },
            "category": {
                "type": "string"
            },
            "summary": {
                "type": "string"
            },
        }
    
        return project_schema

    prompt = """You are an expert in metadata extraction and insight generation. 
    You are helping to build a RAG-based chatbot whose name and description are given below. 
    Using the name and description, generate possible metadata fields that could be extracted from documents that 
    will improve retrieval of documents present in the database. Refer to the example schema below. Return the output 
    as a JSON string. Do not include any explanations in the output.

    Name: {project_name}
    Description: {project_description}
    Example schema:"""
    
    json_schema = """
    {
    "document_type": {
        "type": "string",
    },
    "document_title": {
        "type": "string",
    },
    "author": {
        "type": "string",
    },
    "publication_date": {
        "type": "string",
        "format": "date",
    },
    "abstract": {
        "type": "string",
    },
    "keywords": {
        "type": "array",
        "items": {
            "type": "string"
        }
    },
    "url": {
        "type": "string",
        "format": "uri"
    },
    "language": {
        "type": "string"
    },
    "source": {
        "type": "string"
    },
    "license": {
        "type": "string"
    },
    "category": {
        "type": "string"
    },
    "sub_category": {
        "type": "string"
    }
    }
    """
    
    prompt = prompt.format(project_name=project_name, project_description=project_description) + json_schema
    response = OLLAMA_CLIENT.generate(prompt=prompt, model=LLM)
    json_schema_string = response['response'].strip('```').strip()
    json_schema = []
    try:
        json_schema = json.loads(json_schema_string)
        return json_schema
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return {"error": "Error decoding JSON" + str(e)}
