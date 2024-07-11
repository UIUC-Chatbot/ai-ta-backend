from ollama import Client
from injector import inject

class EmbeddingsService:
    @inject
    def __init__(self):
        self.client = Client(host='https://ollama.ncsa.ai/api/embeddings')

    def create_embeddings(self, text: str):
        response = self.client.embeddings(model='nomic-embed-text:v1.5', prompt=text)
        embeddings = response['embedding']
        return embeddings