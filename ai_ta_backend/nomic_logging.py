import os
import nomic
from nomic import atlas
from nomic import AtlasProject
from langchain.embeddings import OpenAIEmbeddings
import numpy as np
import time
import pandas as pd
import supabase

nomic.login(os.getenv('NOMIC_API_KEY')) # login during start of flask app
NOMIC_MAP_NAME_PREFIX = 'Conversation Map for '

def log_convo_to_nomic(course_name: str, conversation) -> str:
  """
  Logs conversation to Nomic.
  1. Check if map exists for given course
  2. Check if conversation ID exists 
    - if yes, delete and add new data point
    - if no, add new data point
  3. Keep current logic for map doesn't exist - update metadata
  """
  print("in log_convo_to_nomic()")

  print("conversation: ", conversation)
  
  messages = conversation['conversation']['messages']
  user_email = conversation['conversation']['user_email']
  conversation_id = conversation['conversation']['id']

  #print("conversation: ", conversation)
  
  # we have to upload whole conversations
  # check what the fetched data looks like - pandas df or pyarrow table
  # check if conversation ID exists in Nomic, if yes fetch all data from it and delete it. 
  # will have current QA and historical QA from Nomic, append new data and add_embeddings()

  project_name = NOMIC_MAP_NAME_PREFIX + course_name
  start_time = time.monotonic()
  
  try:
    # fetch project metadata and embbeddings
    project = AtlasProject(name=project_name, add_datums_if_exists=True)
    map_metadata_df = project.maps[1].data.df
    map_embeddings_df = project.maps[1].embeddings.latent
    last_id = int(map_metadata_df['id'].values[-1])
    print("last_id: ", last_id)
    
    if conversation_id in map_metadata_df.values:
      print("conversation_id exists")
      
      # store that convo metadata locally
      prev_data = map_metadata_df[map_metadata_df['conversation_id'] == conversation_id]
      prev_index = prev_data.index.values[0]
      embeddings = map_embeddings_df[prev_index-1].reshape(1, 1536)
      prev_convo = prev_data['conversation'].values[0]
      prev_id = prev_data['id'].values[0]
      
      # delete that convo data point from Nomic
      project.delete_data([prev_id])
      
      # prep for new point
      first_message = prev_convo.split("\n")[1].split(": ")[1]
      print("first_message: ", first_message)
    
      # select the last 2 messages and append new convo to prev convo
      messages_to_be_logged = messages[-2:]
      for message in messages_to_be_logged:
        if message['role'] == 'user':
          emoji = "🙋"
        else:
          emoji = "🤖"
        
        prev_convo += "\n>>> " + emoji + message['role'] + ": " + message['content'] + "\n"

      # update metadata
      metadata = [{"course": course_name, "conversation": prev_convo, "conversation_id": conversation_id, 
                    "id": last_id+1, "user_email": user_email, "first_query": first_message}]
    else:
      print("conversation_id does not exist")

      # add new data point
      user_queries = []
      conversation_string = ""
      first_message = messages[0]['content']
      user_queries.append(first_message)

      for message in messages:
        conversation_string += "\n>>> " + emoji + message['role'] + ": " + message['content'] + "\n"

      metadata = [{"course": course_name, "conversation": conversation_string, "conversation_id": conversation_id, 
                    "id": last_id+1, "user_email": user_email, "first_query": first_message}]
      
      # create embeddings
      embeddings_model = OpenAIEmbeddings()
      embeddings = embeddings_model.embed_documents(user_queries)
      
    # add embeddings to the project
    project = atlas.AtlasProject(name=project_name, add_datums_if_exists=True)
    project.add_embeddings(embeddings=np.array(embeddings), data=pd.DataFrame(metadata))
    project.rebuild_maps()
    
  except Exception as e:
    # if project doesn't exist, create it
    print(e)
    result = create_nomic_map(course_name, conversation)
    if result is None:
      print("Nomic map does not exist yet, probably because you have less than 20 queries on your project: ", e)
    else:
      print(f"⏰ Nomic logging runtime: {(time.monotonic() - start_time):.2f} seconds")
      return f"Successfully logged for {course_name}"

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

  # Moved this to the logging function to keep our UI fast.
  # with project.wait_for_project_lock() as project:
  #   project.rebuild_maps()
  
  map = project.get_map(project_name)

  print(f"⏰ Nomic Full Map Retrieval: {(time.monotonic() - start_time):.2f} seconds")

  return {"map_id": f"iframe{map.id}",
          "map_link": map.map_link}

def create_nomic_map(course_name: str, log_data: list):
  """
  Creates a Nomic map for new courses and those which previously had < 20 queries.
  1. fetches supabase conversations for course
  2. appends current embeddings and metadata to it
  2. creates map if there are at least 20 queries
  """
  print("in create_nomic_map()")
  # initialize supabase
  supabase_client = supabase.create_client(  # type: ignore
        supabase_url=os.getenv('SUPABASE_URL'),  # type: ignore
        supabase_key=os.getenv('SUPABASE_API_KEY'))  # type: ignore

  # fetch all conversations with this new course (we expect <=20 conversations, because otherwise the map should be made already)
  response = supabase_client.table("llm-convo-monitor").select("*").eq("course_name", course_name).execute()
  data = response.data
  df = pd.DataFrame(data)
  
  if len(data) < 19:
    return None
  else:
    # get all queries for course and create metadata
    user_queries = []
    metadata = []
    i = 1
    conversation_exists = False

    # current log details
    log_messages = log_data['conversation']['messages']
    log_user_email = log_data['conversation']['user_email']
    log_conversation_id = log_data['conversation']['id']

    for index, row in df.iterrows():
      user_email = row['user_email']
      convo = row['convo']
      messages = convo['messages']
      first_message = messages[0]['content']
      user_queries.append(first_message)

      # create metadata for multi-turn conversation
      conversation = ""
      if message['role'] == 'user':
          emoji = "🙋"
      else:
          emoji = "🤖"
      for message in messages:
        # string of role: content, role: content, ...
        conversation += "\n>>> " + emoji + message['role'] + ": " + message['content'] + "\n"
      
      # append current chat to previous chat if convo already exists
      if convo['id'] == log_conversation_id:
        conversation_exists = True
        if m['role'] == 'user':
          emoji = "🙋"
        else:
          emoji = "🤖"
        for m in log_messages:
          conversation += "\n>>> " + emoji + m['role'] + ": " + m['content'] + "\n"

      # add to metadata
      metadata_row = {"course": row['course_name'], "conversation": conversation, "conversation_id": convo['id'], 
                      "id": i, "user_email": user_email, "first_query": first_message}
      metadata.append(metadata_row)
      i += 1

    # add current log as a new data point if convo doesn't exist
    if not conversation_exists:
      user_queries.append(log_messages[0]['content'])
      conversation = ""
      for message in log_messages:
        if message['role'] == 'user':
          emoji = "🙋"
        else:
          emoji = "🤖"
        conversation += "\n>>> " + emoji + message['role'] + ": " + message['content'] + "\n"
      metadata_row = {"course": course_name, "conversation": conversation, "conversation_id": log_conversation_id, 
                      "id": i, "user_email": log_user_email, "first_query": log_messages[0]['content']}
      metadata.append(metadata_row)

    print("length of metadata: ", len(metadata))
    metadata = pd.DataFrame(metadata)

    embeddings_model = OpenAIEmbeddings() # type: ignore
    embeddings = embeddings_model.embed_documents(user_queries)

    # create Atlas project
    project_name = NOMIC_MAP_NAME_PREFIX + course_name
    index_name = course_name + "_convo_index"
    print("project_name: ", project_name)
    project = atlas.map_embeddings(embeddings=np.array(embeddings), data=metadata, # type: ignore -- this is actually the correc type, the function signature from Nomic is incomplete
                                   id_field='id', build_topic_model=True, topic_label_field='first_query',
                                   name=project_name, colorable_fields=['conversation_id', 'first_query'])
    project.create_index(index_name, build_topic_model=True)
    print("project: ", project)
    return f"Successfully created Nomic map for {course_name}"

if __name__ == '__main__':
  pass
