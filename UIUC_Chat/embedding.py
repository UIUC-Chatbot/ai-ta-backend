import requests
import json
from retry import retry

@retry(tries=10, delay=.25)
def get_embeddings(prompt, model="nomic-embed-text:v1.5", base_url="https://ollama.ncsa.ai/api/embeddings"):

    payload = {
        "model": model,
        "prompt": prompt,
        "options": {
            "num_ctx": 8192
        }
    }

    headers = {
        'Content-Type': 'application/json',
    }

    response = requests.post(base_url, data=json.dumps(payload), headers=headers)

    if response.status_code == 200:
        return response.json()
    # if response.status_code == 500:
    else:
        # Handle errors
        print(f"Error: {response.status_code}, {response.text}")
        return None

# prompt = "The sky is blue because of Rayleigh scattering"
# embeddings = get_embeddings(prompt)

# if embeddings:
#     print(embeddings)
