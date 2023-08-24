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
    self.name_prexif = 'Queries for '

  def nomic_log(self, course_name: str, search_query: str):
    """
    Logs user query and retrieved contexts to Nomic.
    """
    project_name = self.name_prexif + course_name

    embeddings_model = OpenAIEmbeddings() # type: ignore
    embeddings = np.array(embeddings_model.embed_query(search_query)).reshape(1, 1536)
    data = [{'course_name': course_name, 'query': search_query, 'id': time.time()}]

    print("Project name: ", project_name)
    try:
      project = atlas.AtlasProject(name=project_name, add_datums_if_exists=True)
      # mostly async call (0.4 to 0.6 sec)
      project.add_embeddings(embeddings=embeddings, data=data)
    except Exception as e:
      print("Nomic map does not exist yet, probably because you have less than 20 queries on your project: ", e)
    return f"Successfully logged for {course_name}"

  def get_nomic_map(self, course_name: str):
    """
    Returns iframe string of the Nomic map given a course name.
    """
    project_name = self.name_prexif + course_name
    try:
      project = atlas.AtlasProject(name=project_name, add_datums_if_exists=True)
    except Exception as e:
      err = f"Nomic map does not exist yet, probably because you have less than 20 queries on your project: {e}"
      print(err)
      return err
    
    with project.wait_for_project_lock() as project:
        project.rebuild_maps()
    map = project.get_map(project_name)
    return map._iframe()
