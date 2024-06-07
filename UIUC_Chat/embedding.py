import requests
import json

def get_embeddings(prompt, model="nomic-embed-text:v1.5", base_url="https://ollama.ncsa.ai/api/embeddings"):
    # Define the payload
    payload = {
        "model": model,
        "prompt": prompt
    }

    headers = {
        'Content-Type': 'application/json',
    }

    response = requests.post(base_url, data=json.dumps(payload), headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        # Handle errors
        print(f"Error: {response.status_code}, {response.text}")
        return None

# prompt = "The sky is blue because of Rayleigh scattering"
# embeddings = get_embeddings(prompt)

# if embeddings:
#     print(embeddings)
