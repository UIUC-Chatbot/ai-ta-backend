import datetime
import os
import time
from typing import Union

import backoff
import nomic
import numpy as np
import pandas as pd
from injector import inject
from langchain.embeddings import OpenAIEmbeddings
from nomic import AtlasProject, atlas

from ai_ta_backend.database.sql import SQLDatabase
from ai_ta_backend.service.sentry_service import SentryService

LOCK_EXCEPTIONS = [
    'Project is locked for state access! Please wait until the project is unlocked to access embeddings.',
    'Project is locked for state access! Please wait until the project is unlocked to access data.',
    'Project is currently indexing and cannot ingest new datums. Try again later.'
]

def giveup_hdlr(e):
  """
	Function to handle giveup conditions in backoff decorator
	Args: 
			e: Exception raised by the decorated function
	Returns:
			True if we want to stop retrying, False otherwise
	"""
  (e_args,) = e.args
  e_str = e_args['exception']

  print("giveup_hdlr() called with exception:", e_str)
  if e_str in LOCK_EXCEPTIONS:
    return False
  else:
    # self.sentry.capture_exception(e)
    return True


def backoff_hdlr(details):
  """
	Function to handle backup conditions in backoff decorator.
	Currently just prints the details of the backoff.
	"""
  print(
      "\nBacking off {wait:0.1f} seconds after {tries} tries, calling function {target} with args {args} and kwargs {kwargs}"
      .format(**details))


def backoff_strategy():
  """
	Function to define retry strategy. Is usualy defined in the decorator, 
	but passing parameters to it is giving errors.
	"""
  return backoff.expo(base=10, factor=1.5)


class NomicService():

  @inject
  def __init__(self, sentry: SentryService, sql: SQLDatabase):
    nomic.login(os.environ['NOMIC_API_KEY'])
    self.sentry = sentry
    self.sql = sql

  # @backoff.on_exception(backoff_strategy,
  #                       Exception,
  #                       max_tries=5,
  #                       raise_on_giveup=False,
  #                       giveup=giveup_hdlr,
  #                       on_backoff=backoff_hdlr)
  # def log_convo_to_nomic(self, course_name: str, conversation) -> Union[str, None]:
  #   # nomic.login(os.getenv('NOMIC_API_KEY'))  # login during start of flask app
  #   NOMIC_MAP_NAME_PREFIX = 'Conversation Map for '
  #   """
	# 		Logs conversation to Nomic.
	# 		1. Check if map exists for given course
	# 		2. Check if conversation ID exists 
	# 				- if yes, delete and add new data point
	# 				- if no, add new data point
	# 		3. Keep current logic for map doesn't exist - update metadata
	# 		"""

  #   print(f"in log_convo_to_nomic() for course: {course_name}")
  #   print("type of conversation:", type(conversation))
  #   #conversation = json.loads(conversation)
  #   messages = conversation['conversation']['messages']
  #   if 'user_email' not in conversation['conversation']:
  #     user_email = "NULL"
  #   else:
  #     user_email = conversation['conversation']['user_email']
  #   conversation_id = conversation['conversation']['id']

  #   # we have to upload whole conversations
  #   # check what the fetched data looks like - pandas df or pyarrow table
  #   # check if conversation ID exists in Nomic, if yes fetch all data from it and delete it.
  #   # will have current QA and historical QA from Nomic, append new data and add_embeddings()

  #   project_name = NOMIC_MAP_NAME_PREFIX + course_name
  #   start_time = time.monotonic()
  #   emoji = ""

  #   try:
  #     # fetch project metadata and embbeddings
  #     project = AtlasProject(name=project_name, add_datums_if_exists=True)

  #     map_metadata_df = project.maps[1].data.df  # type: ignore
  #     map_embeddings_df = project.maps[1].embeddings.latent
  #     # create a function which returns project, data and embeddings df here
  #     map_metadata_df['id'] = map_metadata_df['id'].astype(int)
  #     last_id = map_metadata_df['id'].max()

  #     if conversation_id in map_metadata_df.values:
  #       # store that convo metadata locally
  #       prev_data = map_metadata_df[map_metadata_df['conversation_id'] == conversation_id]
  #       prev_index = prev_data.index.values[0]
  #       embeddings = map_embeddings_df[prev_index - 1].reshape(1, 1536)
  #       prev_convo = prev_data['conversation'].values[0]
  #       prev_id = prev_data['id'].values[0]
  #       created_at = pd.to_datetime(prev_data['created_at'].values[0]).strftime('%Y-%m-%d %H:%M:%S')

  #       # delete that convo data point from Nomic, and print result
  #       print("Deleting point from nomic:", project.delete_data([str(prev_id)]))

  #       # prep for new point
  #       first_message = prev_convo.split("\n")[1].split(": ")[1]

  #       # select the last 2 messages and append new convo to prev convo
  #       messages_to_be_logged = messages[-2:]
  #       for message in messages_to_be_logged:
  #         if message['role'] == 'user':
  #           emoji = "🙋 "
  #         else:
  #           emoji = "🤖 "

  #         if isinstance(message['content'], list):
  #           text = message['content'][0]['text']
  #         else:
  #           text = message['content']

  #         prev_convo += "\n>>> " + emoji + message['role'] + ": " + text + "\n"

  #       # modified timestamp
  #       current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

  #       # update metadata
  #       metadata = [{
  #           "course": course_name,
  #           "conversation": prev_convo,
  #           "conversation_id": conversation_id,
  #           "id": last_id + 1,
  #           "user_email": user_email,
  #           "first_query": first_message,
  #           "created_at": created_at,
  #           "modified_at": current_time
  #       }]
  #     else:
  #       print("conversation_id does not exist")

  #       # add new data point
  #       user_queries = []
  #       conversation_string = ""

  #       first_message = messages[0]['content']
  #       if isinstance(first_message, list):
  #         first_message = first_message[0]['text']
  #       user_queries.append(first_message)

  #       for message in messages:
  #         if message['role'] == 'user':
  #           emoji = "🙋 "
  #         else:
  #           emoji = "🤖 "

  #         if isinstance(message['content'], list):
  #           text = message['content'][0]['text']
  #         else:
  #           text = message['content']

  #         conversation_string += "\n>>> " + emoji + message['role'] + ": " + text + "\n"

  #       # modified timestamp
  #       current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

  #       metadata = [{
  #           "course": course_name,
  #           "conversation": conversation_string,
  #           "conversation_id": conversation_id,
  #           "id": last_id + 1,
  #           "user_email": user_email,
  #           "first_query": first_message,
  #           "created_at": current_time,
  #           "modified_at": current_time
  #       }]

  #       # create embeddings
  #       embeddings_model = OpenAIEmbeddings(openai_api_type=os.environ['OPENAI_API_TYPE'])
  #       embeddings = embeddings_model.embed_documents(user_queries)

  #     # add embeddings to the project - create a new function for this
  #     project = atlas.AtlasProject(name=project_name, add_datums_if_exists=True)
  #     with project.wait_for_project_lock():
  #       project.add_embeddings(embeddings=np.array(embeddings), data=pd.DataFrame(metadata))
  #       project.rebuild_maps()

  #     print(f"⏰ Nomic logging runtime: {(time.monotonic() - start_time):.2f} seconds")
  #     return f"Successfully logged for {course_name}"

  #   except Exception as e:
  #     if str(e) == 'You must specify a unique_id_field when creating a new project.':
  #       print("Attempting to create Nomic map...")
  #       result = self.create_nomic_map(course_name, conversation)
  #       print("result of create_nomic_map():", result)
  #     else:
  #       # raising exception again to trigger backoff and passing parameters to use in create_nomic_map()
  #       raise Exception({"exception": str(e)})

  def get_nomic_map(self, course_name: str, type: str):
    """
		Returns the variables necessary to construct an iframe of the Nomic map given a course name.
		We just need the ID and URL.
		Example values:
			map link: https://atlas.nomic.ai/map/ed222613-97d9-46a9-8755-12bbc8a06e3a/f4967ad7-ff37-4098-ad06-7e1e1a93dd93
			map id: f4967ad7-ff37-4098-ad06-7e1e1a93dd93
		"""
    # nomic.login(os.getenv('NOMIC_API_KEY'))  # login during start of flask app
    if type.lower() == 'document':
      NOMIC_MAP_NAME_PREFIX = 'Document Map for '
    else:
      NOMIC_MAP_NAME_PREFIX = 'Conversation Map for '

    project_name = NOMIC_MAP_NAME_PREFIX + course_name
    start_time = time.monotonic()

    try:
      project = atlas.AtlasProject(name=project_name, add_datums_if_exists=True)
      map = project.get_map(project_name)

      print(f"⏰ Nomic Full Map Retrieval: {(time.monotonic() - start_time):.2f} seconds")
      return {"map_id": f"iframe{map.id}", "map_link": map.map_link}
    except Exception as e:
      # Error: ValueError: You must specify a unique_id_field when creating a new project.
      if str(e) == 'You must specify a unique_id_field when creating a new project.':  # type: ignore
        print(
            "Nomic map does not exist yet, probably because you have less than 20 queries/documents on your project: ",
            e)
      else:
        print("ERROR in get_nomic_map():", e)
        self.sentry.capture_exception(e)
      return {"map_id": None, "map_link": None}

  def log_to_conversation_map(self, course_name: str):
    """
    This function logs new conversations to existing nomic maps.
    1. Check if nomic map exists
    2. If no, create it
    3. If yes, fetch all conversations since last upload and log it
    """


  def create_conversation_map(self, course_name: str):
    """
    This function creates a conversation map for a given course from scratch.
    """
    nomic.login(os.getenv('NOMIC_API_KEY'))
    NOMIC_MAP_NAME_PREFIX = 'Conversation Map for '
    try:
      # check if map exists
      response = self.sql.getConvoMapFromProjects(course_name)
      print("Response from supabase: ", response.data)
      if response.data[0]['convo_map_id']:
        return "Map already exists for this course."

      # if no, fetch total count of records
      response = self.sql.getCountFromLLMConvoMonitor(course_name)

      # if <20, return message that map cannot be created
      if not response.count:
        return "No conversations found for this course."
      elif response.count < 20:
        return "Cannot create a map because there are less than 20 conversations in the course."

      # if >20, iteratively fetch records in batches of 100
      total_convo_count = response.count
      print("Total number of conversations in Supabase: ", total_convo_count)
        
      first_id = response.data[0]['id'] - 1
      combined_dfs = []
      current_convo_count = 0
      convo_count = 0
      first_batch = True
      project_name = NOMIC_MAP_NAME_PREFIX + course_name

      # iteratively query in batches of 50
      while current_convo_count < total_convo_count:
        response = self.sql.getAllConversationsBetweenIds(course_name, first_id, 0, 100)
        print("Response count: ", len(response.data))
        if len(response.data) == 0:
          break
        df = pd.DataFrame(response.data)
        combined_dfs.append(df)
        current_convo_count += len(response.data)
        convo_count += len(response.data)
        print(current_convo_count)

        if convo_count >= 500:
          # concat all dfs from the combined_dfs list
          final_df = pd.concat(combined_dfs, ignore_index=True)
          # prep data for nomic upload
          embeddings, metadata = self.data_prep_for_convo_map(final_df)

          if first_batch:
            # create a new map
            print("Creating new map...")
            index_name = course_name + "_convo_index"
            topic_label_field = "first_query"
            colorable_fields = ["user_email", "first_query", "conversation_id", "created_at"]
            result = self.create_map(embeddings, metadata, project_name, index_name, topic_label_field, colorable_fields)

            if result == "success":
              # update flag
              first_batch = False
              # log project info to supabase
              project = AtlasProject(name=project_name, add_datums_if_exists=True)
              project_id = project.id
              last_id = int(final_df['id'].iloc[-1])
              project_info = {'course_name': course_name, 'convo_map_id': project_id, 'last_uploaded_convo_id': last_id}
              # if entry already exists, update it
              projects_record = self.sql.getConvoMapFromProjects(course_name)
              if projects_record.data:
                project_response = self.sql.updateProjects(course_name, project_info)
              else:
                project_response = self.sql.insertProjectInfo(project_info)
              print("Update response from supabase: ", project_response)
          else:
            # append to existing map
            print("Appending data to existing map...")
            project = AtlasProject(name=project_name, add_datums_if_exists=True)
            result = self.append_to_map(embeddings, metadata, project_name)
            if result == "success":
              last_id = int(final_df['id'].iloc[-1])
              project_response = self.sql.updateProjects(course_name, project_info)
              print("Update response from supabase: ", project_response)
          
          # reset variables
          combined_dfs = []
          convo_count = 0
          print("Records uploaded: ", current_convo_count)
          
        # set first_id for next iteration
        try:
          print("response: ", response.data[-1]['id'])
        except:
          print("response: ", response.data)
        first_id = response.data[-1]['id'] + 1

      print("Convo count: ", convo_count)
      # upload last set of convos
      if convo_count > 0:
        print("Uploading last set of conversations...")
        final_df = pd.concat(combined_dfs, ignore_index=True)
        embeddings, metadata = self.data_prep_for_convo_map(final_df)
        if first_batch:
          # create map
          index_name = course_name + "_convo_index"
          topic_label_field = "first_query"
          colorable_fields = ["user_email", "first_query", "conversation_id", "created_at"]
          result = self.create_map(embeddings, metadata, project_name, index_name, topic_label_field, colorable_fields)

        else:
          # append to map
          print("in map append")
          result = self.append_to_map(embeddings, metadata, project_name)
          
        if result == "success":
          print("last map append successful")
          last_id = int(final_df['id'].iloc[-1])
          project = AtlasProject(name=project_name, add_datums_if_exists=True)
          project_id = project.id
          project_info = {'course_name': course_name, 'convo_map_id': project_id, 'last_uploaded_convo_id': last_id}
          print("Project info: ", project_info)
          # if entry already exists, update it
          projects_record = self.sql.getConvoMapFromProjects(course_name)
          if projects_record.data:
            project_response = self.sql.updateProjects(course_name, project_info)
          else:
            project_response = self.sql.insertProjectInfo(project_info)
          print("Response from supabase: ", project_response)
            
      # rebuild the map
      self.rebuild_map(course_name, "conversation")
      return "success"
    except Exception as e:
      print(e)
      self.sentry.capture_exception(e)
      return "Error in creating conversation map:" + str(e)


  
    
  
  ## -------------------------------- SUPPLEMENTARY MAP FUNCTIONS --------------------------------- ##

  def rebuild_map(self, course_name:str, map_type:str):
    """
    This function rebuilds a given map in Nomic.
    """
    print("in rebuild_map()")
    nomic.login(os.getenv('NOMIC_API_KEY'))

    if map_type.lower() == 'document':
      NOMIC_MAP_NAME_PREFIX = 'Document Map for '
    else:
      NOMIC_MAP_NAME_PREFIX = 'Conversation Map for '

    try:
      # fetch project from Nomic
      project_name = NOMIC_MAP_NAME_PREFIX + course_name
      project = AtlasProject(name=project_name, add_datums_if_exists=True)

      if project.is_accepting_data:
        project.rebuild_maps()
      return "success"
    except Exception as e:
      print(e)
      self.sentry.capture_exception(e)
      return "Error in rebuilding map: {e}"
    

  def create_map(self, embeddings, metadata, map_name, index_name, topic_label_field, colorable_fields):
    """
		Generic function to create a Nomic map from given parameters.
		Args:
			embeddings: np.array of embeddings
			metadata: pd.DataFrame of metadata
			map_name: str
			index_name: str
			topic_label_field: str
			colorable_fields: list of str
		"""
    nomic.login(os.environ['NOMIC_API_KEY'])
    print("in create_map()")
    try:
      project = atlas.map_embeddings(embeddings=embeddings,
                                     data=metadata,
                                     id_field="id",
                                     build_topic_model=True,
                                     name=map_name,
                                     topic_label_field=topic_label_field,
                                     colorable_fields=colorable_fields,
                                     add_datums_if_exists=True)
      project.create_index(index_name, build_topic_model=True)
      return "success"
    except Exception as e:
      print(e)
      return "Error in creating map: {e}"

  def append_to_map(self, embeddings, metadata, map_name):
    """
		Generic function to append new data to an existing Nomic map.
		Args:
			embeddings: np.array of embeddings
			metadata: pd.DataFrame of Nomic upload metadata
			map_name: str
		"""
    nomic.login(os.environ['NOMIC_API_KEY'])
    try:
      project = atlas.AtlasProject(name=map_name, add_datums_if_exists=True)
      with project.wait_for_project_lock():
        project.add_embeddings(embeddings=embeddings, data=metadata)
      return "Successfully appended to Nomic map"
    except Exception as e:
      print(e)
      return "Error in appending to map: {e}"
    

  def data_prep_for_convo_map(self, df: pd.DataFrame):
    """
		This function prepares embeddings and metadata for nomic upload in conversation map creation.
		Args:
			df: pd.DataFrame - the dataframe of documents from Supabase
		Returns:
			embeddings: np.array of embeddings
			metadata: pd.DataFrame of metadata
		"""
    print("in data_prep_for_convo_map()")
    try:
      metadata = []
      embeddings = []
      user_queries = []

      for _index, row in df.iterrows():
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        created_at = datetime.datetime.strptime(row['created_at'], "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%Y-%m-%d %H:%M:%S")
        conversation_exists = False
        conversation = ""
        emoji = ""

        if row['user_email'] is None:
          user_email = ""
        else:
          user_email = row['user_email']

        messages = row['convo']['messages']
        first_message = messages[0]['content']
        # some conversations include images, so the data structure is different
        if isinstance(first_message, list):
          first_message = first_message[0]['text']
        user_queries.append(first_message)

        # construct metadata for multi-turn conversation
        for message in messages:
          if message['role'] == 'user': 
            emoji = "🙋 "
          else:
            emoji = "🤖 "

          if isinstance(message['content'], list):
            text = message['content'][0]['text']
          else:
            text = message['content']

          conversation += "\n>>> " + emoji + message['role'] + ": " + text + "\n"
          
        meta_row = {
            "course": row['course_name'],
            "conversation": conversation,
            "conversation_id": row['convo']['id'],
            "id": row['id'],
            "user_email": user_email,
            "first_query": first_message,
            "created_at": created_at,
            "modified_at": current_time
          }
          
        metadata.append(meta_row)

      embeddings_model = OpenAIEmbeddings(openai_api_type="openai",
                                              openai_api_base="https://api.openai.com/v1/",
                                              openai_api_key=os.environ['VLADS_OPENAI_KEY'])
      embeddings = embeddings_model.embed_documents(user_queries)
          
      metadata = pd.DataFrame(metadata)
      embeddings = np.array(embeddings)
      return embeddings, metadata

    except Exception as e:
      print("Error in data_prep_for_convo_map():", e)
      self.sentry.capture_exception(e)
      return None, None

  def delete_from_document_map(self, project_id: str, ids: list):
    """
		This function is used to delete datapoints from a document map.
		Currently used within the delete_data() function in vector_database.py
		Args:
			course_name: str
			ids: list of str
		"""
    print("in delete_from_document_map()")

    try:
      # fetch project from Nomic
      project = AtlasProject(project_id=project_id, add_datums_if_exists=True)

      # delete the ids from Nomic
      print("Deleting point from document map:", project.delete_data(ids))
      with project.wait_for_project_lock():
        project.rebuild_maps()
      return "Successfully deleted from Nomic map"
    except Exception as e:
      print(e)
      self.sentry.capture_exception(e)
      return "Error in deleting from document map: {e}"