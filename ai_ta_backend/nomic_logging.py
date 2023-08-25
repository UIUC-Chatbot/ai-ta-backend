import os
import nomic
from nomic import atlas
from langchain.embeddings import OpenAIEmbeddings
import numpy as np
import time
import pandas as pd
import supabase

nomic.login(os.getenv('NOMIC_API_KEY')) # login during start of flask app
NOMIC_MAP_NAME_PREFIX = 'Queries for '

def log_query_to_nomic(course_name: str, search_query: str) -> str:
  """
  Logs user query and retrieved contexts to Nomic. Must have more than 20 queries to get a map.

  TODO: Better handle courses that have less than 20 queries
  """

  project_name = NOMIC_MAP_NAME_PREFIX + course_name
  start_time = time.monotonic()

  embeddings_model = OpenAIEmbeddings() # type: ignore
  embeddings = np.array(embeddings_model.embed_query(search_query)).reshape(1, 1536)
  data = [{'course_name': course_name, 'query': search_query, 'id': time.time()}]

  try:
    # slow call, about 0.6 sec
    project = atlas.AtlasProject(name=project_name, add_datums_if_exists=True)
    # mostly async call (0.35 to 0.5 sec)
    project.add_embeddings(embeddings=embeddings, data=data)

    # required to keep maps fresh (or we could put on fetch side, but then our UI is slow)
    project.rebuild_maps()
  except Exception as e:
    print("Nomic map does not exist yet, probably because you have less than 20 queries on your project: ", e)
  
  print(f"⏰ Nomic logging runtime: {(time.monotonic() - start_time):.2f} seconds")
  return f"Successfully logged for {course_name}"

def get_nomic_map(course_name: str):
  """
  Returns the variables necessary to construct an iframe of the Nomic map given a course name.
  We just need the ID and URL.
  Example values:
    map link: https://atlas.nomic.ai/map/ed222613-97d9-46a9-8755-12bbc8a06e3a/f4967ad7-ff37-4098-ad06-7e1e1a93dd93
    map id: f4967ad7-ff37-4098-ad06-7e1e1a93dd93
  """
  project_name = NOMIC_MAP_NAME_PREFIX + course_name
  start_time = time.monotonic()

  try:
    project = atlas.AtlasProject(name=project_name, add_datums_if_exists=True)
  except Exception as e:
    err = f"Nomic map does not exist yet, probably because you have less than 20 queries on your project: {e}"
    print(err)
    return {"map_id": None, "map_link": None}


  # with project.wait_for_project_lock() as project:
  #   rebuild_start_time = time.monotonic()
  #   project.rebuild_maps()
  #   print(f"⏰ Nomic _only_ map rebuild: {(time.monotonic() - rebuild_start_time):.2f} seconds")
  
  map = project.get_map(project_name)

  print(f"⏰ Nomic Full Map Retrieval: {(time.monotonic() - start_time):.2f} seconds")

  return {"map_id": f"iframe{map.id}",
          "map_link": map.map_link}

def create_nomic_map():
  """
  Creates a Nomic map for new courses and those which previously had < 20 queries.
  """
  # 1. maintain a list of courses with maps.
  # 2. fetch conversation data for all the courses.
  # 3. skip courses which already have maps, and create maps for the rest.
  # 4. add the course to the list of courses which already have maps.
  print("inside nomic map creation")
  courses_with_maps = ['gpt4', 'badm_550_ashley', 'ece120', 'badm-567-v3', 'new-weather', 
  'gies-online-mba-v2', 'frontend', 'ECE220FA23', 'ECE408FA23', 'ece408', 'farmdoc_test_kastan-v1', 
  'NPRE247', 'your-awesome-course', 'pract', 'ece120FL22', 'Law794-TransactionalDraftingAlam', 
  'NCSA', 'NCSADelta', 'NuclGPT-v1']
  
  # initialize supabase
  url = os.getenv('SUPABASE_URL')
  key = os.getenv('SUPABASE_API_KEY')
  supabase_client = supabase.Client(url, key)

  # fetch all conversations from supabase
  response = supabase_client.table("llm-convo-monitor").select("*").execute()
  data = response.data
  all_courses_df = df = pd.DataFrame(data)
  course_names_from_db = df['course_name'].unique()

  # initialize langchain embeddings
  embeddings_model = OpenAIEmbeddings()

  for course in course_names_from_db:
    if course is None or course in courses_with_maps:
      continue

    # get all queries for course and create metadata
    user_queries = []
    metadata = []

    course_df = all_courses_df[all_courses_df['course_name'] == course]['convo']

    i = 1
    for convo in course_df:
      # extract all messages from convo
      messages = convo['messages']

      # extract queries for user role from messages
      for message in messages:
        if message['role'] == 'user' and message['content'] != '':
          user_queries.append(message['content'])
          metadata.append({'course_name': course, 'query': message['content'], 'id': i})
          i += 1
    
    if len(user_queries) < 20:
      print("course has less than 20 queries, skipping: ", course)
      print(len(courses_with_maps))
      continue
    else:
      courses_with_maps.append(course)

    # convert query and context to embeddings
    metadata = pd.DataFrame(metadata)
    embeddings = embeddings_model.embed_documents(user_queries)
    embeddings = np.array(embeddings)
    print(embeddings.shape)

    # create Atlas project
    project_name = NOMIC_MAP_NAME_PREFIX + course
    index_name = course + "_index"
    project = atlas.map_embeddings(embeddings=np.array(embeddings), data=metadata,
                                   id_field='id', build_topic_model=True, topic_label_field='query',
                                   name=project_name, colorable_fields=['query'])
    project.create_index(index_name, build_topic_model=True)
    print(project.maps)
    print("total projects with maps: ", len(courses_with_maps))


