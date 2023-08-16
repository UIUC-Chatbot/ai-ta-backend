import os
import nomic
from nomic import atlas
from langchain.embeddings import OpenAIEmbeddings
import numpy as np
import time

class DataLog():
    def __init__(self):
        self.login = nomic.login(os.getenv('NOMIC_API_KEY'))

    def nomic_log(self, course_name:str, search_query:str, retrieved_contexts)-> str:
        """
        Logs user query and retrieved contexts to Nomic.
        """
        print("course_name: ", course_name)
        print("search_query: ", search_query)
        print("retrieved_contexts: ", len(retrieved_contexts))

        # concat all retrieved contexts into one string
        context_string = ""
        for context in retrieved_contexts:
            context_string += context['text'] + " "
        
        #print("context_string: ", context_string)

        # convert query and context to embeddings
        embeddings_model = OpenAIEmbeddings()
        embeddings = embeddings_model.embed_documents([search_query, context_string])

        data = [{'course_name': course_name, 'query': search_query, 'id': time.time()}, 
                 {'course_name': course_name, 'query': context_string, 'id': time.time()}]

        print("len of data: ", len(data))
        print("len of embeddings: ", len(embeddings))
        print(data)
        
        project = atlas.AtlasProject(name="User Query Text Viz", add_datums_if_exists=True)
        map = project.get_map('Search Query Viz')
        print(project.name)
        print(map)

        with project.wait_for_project_lock() as project:
            project.add_embeddings(embeddings=np.array(embeddings), data=data)
            project.rebuild_maps()

        print("done")
        # log to Nomic
        return "WIP"