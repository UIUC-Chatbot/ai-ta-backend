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

  def nomic_log(self, course_name: str, search_query: str):
    """
    Logs user query and retrieved contexts to Nomic.
    """
    embeddings_model = OpenAIEmbeddings()
    embeddings = np.array(embeddings_model.embed_query(search_query)).reshape(1, 1536)

    # for testing:
    # reshaped_embeddings = np.random.rand(1, 1536)

    data = [{'course_name': course_name, 'query': search_query, 'id': time.time()}]

    # todo fix
    project_name = "User Query Text Viz for " + course_name

    print("Project name: ", project_name)
    try:
      project = atlas.AtlasProject(name=project_name, add_datums_if_exists=True)
      # map = project.get_map(project_name)

      # Try this for async.
      project.add_embeddings(embeddings=embeddings, data=data)
      # with project.wait_for_project_lock() as project:
      #     project.rebuild_maps()
    except Exception as e:
      print("Nomic map does not exist yet: ", e)

    #return "Successfully logged"

  def get_nomic_map(self, course_name: str):
    """
    Returns iframe string of the Nomic map given a course name.
    """
    map_name = "User Query Text Viz for " + course_name
    project = atlas.AtlasProject(name=map_name)
    map = project.get_map(map_name)
    return map._iframe()
