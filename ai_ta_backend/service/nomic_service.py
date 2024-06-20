import datetime
import os
import time

from injector import inject
from langchain.embeddings.openai import OpenAIEmbeddings
import nomic
from nomic import atlas
from nomic import AtlasProject
import numpy as np
import pandas as pd

from ai_ta_backend.database.sql import SQLAlchemyDatabase
from ai_ta_backend.service.sentry_service import SentryService

LOCK_EXCEPTIONS = [
    'Project is locked for state access! Please wait until the project is unlocked to access embeddings.',
    'Project is locked for state access! Please wait until the project is unlocked to access data.',
    'Project is currently indexing and cannot ingest new datums. Try again later.'
]


class NomicService():

  @inject
  def __init__(self, sentry: SentryService, sql: SQLAlchemyDatabase):
    nomic.login(os.environ['NOMIC_API_KEY'])
    self.sentry = sentry
    self.sql = sql

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
        print("Nomic map does not exist yet, probably because you have less than 20 queries/documents on your project: ", e)
      else:
        print("ERROR in get_nomic_map():", e)
        self.sentry.capture_exception(e)
      return {"map_id": None, "map_link": None}

  def log_to_conversation_map(self, course_name: str, conversation):
    """
    This function logs new conversations to existing nomic maps.
    1. Check if nomic map exists
    2. If no, create it
    3. If yes, fetch all conversations since last upload and log it
    """
    nomic.login(os.getenv('NOMIC_API_KEY'))
    NOMIC_MAP_NAME_PREFIX = 'Conversation Map for '
    try:
      # check if map exists
      response = self.sql.getConvoMapFromProjects(course_name)
      print("Response from supabase: ", response.data)

      # entry not present in projects table
      if not response.data:
        print("Map does not exist for this course. Redirecting to map creation...")
        return self.create_conversation_map(course_name)

      # entry present for doc map, but not convo map
      elif response.data[0].convo_map_id is not None:
        print("Map does not exist for this course. Redirecting to map creation...")
        return self.create_conversation_map(course_name)

      project_id = response.data[0].convo_map_id
      last_uploaded_convo_id: int = int(str(response.data[0].last_uploaded_convo_id))

      # check if project is accepting data
      project = AtlasProject(project_id=project_id, add_datums_if_exists=True)
      if not project.is_accepting_data:
        return "Project is currently indexing and cannot ingest new datums. Try again later."

      # fetch count of conversations since last upload
      response = self.sql.getCountFromLLMConvoMonitor(course_name, last_id=last_uploaded_convo_id)
      total_convo_count = response.count
      print("Total number of unlogged conversations in Supabase: ", total_convo_count)

      if total_convo_count == 0:
        # log to an existing conversation
        existing_convo = self.log_to_existing_conversation(course_name, conversation)
        return existing_convo

      first_id = last_uploaded_convo_id
      combined_dfs = []
      current_convo_count = 0
      convo_count = 0

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
          # append to existing map
          print("Appending data to existing map...")
          result = self.append_to_map(embeddings, metadata, NOMIC_MAP_NAME_PREFIX + course_name)
          if result == "success":
            last_id = int(final_df['id'].iloc[-1])
            project_info = {'course_name': course_name, 'convo_map_id': project_id, 'last_uploaded_convo_id': last_id}
            project_response = self.sql.updateProjects(course_name, project_info)
            print("Update response from supabase: ", project_response)
          # reset variables
          combined_dfs = []
          convo_count = 0
          print("Records uploaded: ", current_convo_count)

        # set first_id for next iteration
        first_id = int(str(response.data[-1].id)) + 1

      # upload last set of convos
      if convo_count > 0:
        print("Uploading last set of conversations...")
        final_df = pd.concat(combined_dfs, ignore_index=True)
        embeddings, metadata = self.data_prep_for_convo_map(final_df)
        result = self.append_to_map(embeddings, metadata, NOMIC_MAP_NAME_PREFIX + course_name)
        if result == "success":
          last_id = int(final_df['id'].iloc[-1])
          project_info = {'course_name': course_name, 'convo_map_id': project_id, 'last_uploaded_convo_id': last_id}
          project_response = self.sql.updateProjects(course_name, project_info)
          print("Update response from supabase: ", project_response)

      # rebuild the map
      self.rebuild_map(course_name, "conversation")
      return "success"

    except Exception as e:
      print(e)
      self.sentry.capture_exception(e)
      return "Error in logging to conversation map: {e}"

  def log_to_existing_conversation(self, course_name: str, conversation):
    """
    This function logs follow-up questions to existing conversations in the map.
    """
    print(f"in log_to_existing_conversation() for course: {course_name}")

    try:
      conversation_id = conversation['id']

      # fetch id from supabase
      incoming_id_response = self.sql.getConversation(course_name, key="convo_id", value=conversation_id)

      project_name = 'Conversation Map for ' + course_name
      project = AtlasProject(name=project_name, add_datums_if_exists=True)

      prev_id = str(incoming_id_response.data[0].id)
      uploaded_data = project.get_data(ids=[prev_id])  # fetch data point from nomic
      prev_convo = uploaded_data[0]['conversation']

      # update conversation
      messages = conversation['messages']
      messages_to_be_logged = messages[-2:]

      for message in messages_to_be_logged:
        if message['role'] == 'user':
          emoji = "🙋 "
        else:
          emoji = "🤖 "

        if isinstance(message['content'], list):
          text = message['content'][0]['text']
        else:
          text = message['content']

        prev_convo += "\n>>> " + emoji + message['role'] + ": " + text + "\n"

      # create embeddings of first query
      embeddings_model = OpenAIEmbeddings(openai_api_type="openai",
                                          openai_api_base="https://api.openai.com/v1/",
                                          openai_api_key=os.environ['VLADS_OPENAI_KEY'],
                                          openai_api_version="2020-11-07")
      embeddings = embeddings_model.embed_documents([uploaded_data[0]['first_query']])

      # modified timestamp
      current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      uploaded_data[0]['conversation'] = prev_convo
      uploaded_data[0]['modified_at'] = current_time

      metadata = pd.DataFrame(uploaded_data)
      embeddings = np.array(embeddings)

      print("Metadata shape:", metadata.shape)
      print("Embeddings shape:", embeddings.shape)

      # deleting existing map
      print("Deleting point from nomic:", project.delete_data([prev_id]))

      # re-build map to reflect deletion
      project.rebuild_maps()

      # re-insert updated conversation
      result = self.append_to_map(embeddings, metadata, project_name)
      print("Result of appending to existing map:", result)

      return "success"

    except Exception as e:
      print("Error in log_to_existing_conversation():", e)
      self.sentry.capture_exception(e)
      return "Error in logging to existing conversation: {e}"

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
      if response.data:
        if response.data[0].convo_map_id is not None:
          return "Map already exists for this course."

      # if no, fetch total count of records
      response = self.sql.getCountFromLLMConvoMonitor(course_name, last_id=0)

      # if <20, return message that map cannot be created
      if not response.count:
        return "No conversations found for this course."
      elif response.count < 20:
        return "Cannot create a map because there are less than 20 conversations in the course."

      # if >20, iteratively fetch records in batches of 100
      total_convo_count = response.count
      print("Total number of conversations in Supabase: ", total_convo_count)

      first_id = int(str(response.data[0].id)) - 1
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
              print("map append successful")
              last_id = int(final_df['id'].iloc[-1])
              project_info = {'last_uploaded_convo_id': last_id}
              project_response = self.sql.updateProjects(course_name, project_info)
              print("Update response from supabase: ", project_response)

          # reset variables
          combined_dfs = []
          convo_count = 0
          print("Records uploaded: ", current_convo_count)

        # set first_id for next iteration
        try:
          print("response: ", response.data[-1].id)
        except Exception as e:
          print("response: ", response.data)
        first_id = int(str(response.data[-1].id)) + 1

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

  def rebuild_map(self, course_name: str, map_type: str):
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
      return "success"
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
        conversation = ""
        emoji = ""

        if row['user_email'] is None:
          user_email = ""
        else:
          user_email = row['user_email']

        messages = row['convo']['messages']
        first_message = ""

        # some conversations include images, so the data structure is different
        if isinstance(messages[0]['content'], list):
          if 'text' in messages[0]['content'][0]:
            first_message = messages[0]['content'][0]['text']
            #print("First message:", first_message)
        else:
          first_message = messages[0]['content']
        user_queries.append(first_message)

        # construct metadata for multi-turn conversation
        for message in messages:
          text = ""
          if message['role'] == 'user':
            emoji = "🙋 "
          else:
            emoji = "🤖 "

          if isinstance(message['content'], list):

            if 'text' in message['content'][0]:
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
        #print("Metadata row:", meta_row)
        metadata.append(meta_row)

      embeddings_model = OpenAIEmbeddings(openai_api_type="openai",
                                          openai_api_base="https://api.openai.com/v1/",
                                          openai_api_key=os.environ['VLADS_OPENAI_KEY'],
                                          openai_api_version="2020-11-07")
      embeddings = embeddings_model.embed_documents(user_queries)

      metadata = pd.DataFrame(metadata)
      embeddings = np.array(embeddings)
      print("Metadata shape:", metadata.shape)
      print("Embeddings shape:", embeddings.shape)
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
