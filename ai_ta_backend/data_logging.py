import os
import nomic
from nomic import atlas
from langchain.embeddings import OpenAIEmbeddings
import numpy as np
import time
import asyncio

class DataLog():
    def __init__(self):
        self.login = nomic.login(os.getenv('NOMIC_API_KEY'))

    def nomic_log(self, course_name:str, search_query:str):
        """
        Logs user query and retrieved contexts to Nomic.
        """
        # convert query and context to embeddings
        embeddings_model = OpenAIEmbeddings()
        embeddings = embeddings_model.embed_query(search_query)
        embeddings = np.array(embeddings)
        reshaped_embeddings = embeddings.reshape(1, 1536)

        data = [{'course_name': course_name, 'query': search_query, 'id': time.time()}]

        project = atlas.AtlasProject(name="User Query Text Viz 2", add_datums_if_exists=True)
        map = project.get_map('User Query Text Viz 2')
        print("Tags: ", map.tags) # displays id field
        print("Topics: ", map.topics) # displays topic depth

        with project.wait_for_project_lock() as project:
            project.add_embeddings(embeddings=reshaped_embeddings, data=data)
            project.rebuild_maps()

        #return "Successfully logged"
        