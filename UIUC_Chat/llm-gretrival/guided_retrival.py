import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("AZURE_OPENAI_KEY")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
deployment = os.getenv("DEPLOYMENT")
api_version = os.getenv("OPENAI_API_VERSION")
openai_api = os.getenv("OPENAI_API")

client = OpenAI(api_key=openai_api)

tools = [{
    "type": "function",
    "function": {
        "name": "keep_current_chunk",
        "description": "Check if the current chunk of context is relevant to the query",
        "parameters": {
            "type": "object",
            "properties": {
                "keep": {
                    "type": "boolean",
                    "description": "Whether to keep the current chunk or not"
                }
            },
            "required": ["keep"]
        }
    },
    "required": True
}, {
    "type": "function",
    "function": {
        "name": "check_previous_chunk",
        "description": "Check if the previous chunk of context is relevant to the query",
        "parameters": {
            "type": "object",
            "properties": {
                "check_previous": {
                    "type": "boolean",
                    "description": "True if the previous chunk is relevant, False otherwise"
                }
            },
            "required": ["check_previous"]
        }
    },
}, {
    "type": "function",
    "function": {
        "name": "check_next_chunk",
        "description": "Check if the next chunk of context is relevant to the query",
        "parameters": {
            "type": "object",
            "properties": {
                "check_next": {
                    "type": "boolean",
                    "description": "True if the next chunk is relevant, False otherwise"
                }
            },
            "required": ["check_next"]
        }
    }
}, {
    "type": "function",
    "function": {
        "name": "go_to_URL",
        "description": "Click link or go to URL referenced in chunk.",
        "parameters": {
            "type": "object",
            "properties": {
                "go_to_URL": {
                    "type": "boolean",
                    "description": "Whether to go to the URL or not"
                }
            },
            "required": ["go_to_URL"]
        }
    }
}]

query = "What is the name of Polly's son?"
chunks = [
    "The Blinders' dominance came about from beating rivals, including the 'Sloggers', 'a pugilistic term for someone who could strike a heavy blow in the ring', whom they fought for territory in Birmingham and its surrounding districts.",
    "Britain is a mixture of despair and hedonism in 1919 in the aftermath of the Great War. Returning soldiers, newly minted revolutions and criminal gangs are fighting for survival in a nation rocked by economic upheaval.",
    "Polly's son, Michael Gray, was taken away when he was a baby. He was raised by a family in Australia. He was brought back to Birmingham by Polly in season 2."
]

messages = [{
    "role":
        "system",
    "content": (
        "You are an expert in information retrieval. Your task is to evaluate the relevance of a given text chunk to a specific research question. "
        "You have four functions at your disposal: 'keep_current_chunk', 'check_previous_chunk', 'check_next_chunk', and 'go_to_url'. "
        "Always use 'keep_current_chunk' to determine if the current chunk is relevant. Then, consider using 'check_previous_chunk' or 'check_next_chunk' or 'go_to_url'. "
        "When using 'check_previous_chunk', if you find previous chunk relevant to the research question, set 'check_previous' to 'True', otherwise false. "
        "When using 'check_next_chunk', if you find next chunk relevant to the research question, set 'check_next' to 'True', otherwise false. "
        "Use 'go_to_url' if the chunk suggests checking an external link.")
}, {
    "role":
        "user",
    "content": (
        f"Research Question: '{query}'\n\n"
        f"Current Text Chunk: '{chunks[1]}'\n\n"
        "Evaluate the relevance of the current chunk to the research question. Determine if the current chunk should be kept. "
        "Also, decide whether to check the previous chunk by calling 'check_previous_chunk', or the next chunk by calling 'check_next_chunk', or whether to follow an external link using the respective functions. "
        "Make sure you call other functions and determine if previous or next chunks are relevant to the research question."
    )
}]

completion = client.chat.completions.create(
    model='gpt-4o',
    messages=messages,
    tools=tools,
    # tool_choice={"type": "function", "function": {"name": "keep_current_chunk"}},
)

print(completion)
