import json

import requests
from retry import retry


@retry(tries=10, delay=.25)
def get_embeddings(prompt, model="nomic-embed-text:v1.5", base_url="https://ollama.ncsa.ai/api/embeddings"):

  payload = {"model": model, "prompt": prompt, "options": {"num_ctx": 8192}}

  headers = {
      'Content-Type': 'application/json',
  }

  response = requests.post(base_url, data=json.dumps(payload), headers=headers)

  if response.status_code == 200:
    embedding_json = response.json()
    if "embedding" in embedding_json:
      embeddings = embedding_json["embedding"]
      if isinstance(embeddings, list):
        return embeddings
      else:
        print("Error: Embeddings is not a list")
    else:
      print("Error: 'embeddings' key not found in response")
  else:
    print(f"Embedding error: {response.status_code}, {response.text}")

  return None


# prompt = "The sky is blue because of Rayleigh scattering"
# embeddings = get_embeddings(prompt)

# if embeddings:
#     print(embeddings)
