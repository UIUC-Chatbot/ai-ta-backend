import datetime
import os
import time
from typing import Union

import backoff
import nomic
import numpy as np
import pandas as pd
from injector import inject
from langchain.embeddings.openai import OpenAIEmbeddings
from nomic import AtlasDataset, atlas

from ai_ta_backend.database.sql import SQLDatabase
from ai_ta_backend.service.sentry_service import SentryService

LOCK_EXCEPTIONS = [
    'Project is locked for state access! Please wait until the project is unlocked to access embeddings.',
    'Project is locked for state access! Please wait until the project is unlocked to access data.',
    'Project is currently indexing and cannot ingest new datums. Try again later.'
]


class NomicService():

  @inject
  def __init__(self, sentry: SentryService, sql: SQLDatabase):
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
    project_name = project_name.replace(" ", "-").lower()
    start_time = time.monotonic()

    try:
      project = AtlasDataset(project_name)
      map = project.get_map(course_name + "_convo_index")

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
    
  def update_conversation_maps(self):
    """
    This function updates all conversation maps in UIUC.Chat. To be called via a CRON job.
    """
    try:
      # fetch all projects from SQL
      response = self.sql.getAllProjects()
      projects = response.data

      for project in projects:
        if not project['convo_map_id']:
          # need to create a new conversation map
          print("Creating new conversation map for course: ", project['course_name'])
          status = self.create_conversation_map(project['course_name'])
          print("Status of conversation map creation: ", status)
          
        else:
          print("Updating existing conversation map for course: ", project['course_name'])
          # check the last uploaded conversation id
          last_uploaded_convo_id = project['last_uploaded_convo_id']
          response = self.sql.getCountFromLLMConvoMonitor(project['course_name'], last_id=last_uploaded_convo_id)
          total_convo_count = response.count

          if total_convo_count == 0:
            print("No new conversations to log.")
            continue
          else:
            print("Total number of unlogged conversations in Supabase: ", total_convo_count)
            current_convo_count = 0
            combined_dfs = []
            while current_convo_count < total_convo_count:
              response = self.sql.getAllConversationsBetweenIds(project['course_name'], last_uploaded_convo_id, 0, 100)
              if len(response.data) == 0:
                break
              curr_df = pd.DataFrame(response.data)
              combined_dfs.append(curr_df)
              current_convo_count += len(response.data)

            # concat all dfs from the combined_dfs list
            final_df = pd.concat(combined_dfs, ignore_index=True)
            # prep data for nomic upload
            embeddings, metadata = self.data_prep_for_convo_map(final_df)

            # append to existing map
            print("Appending data to existing map...")
            result = self.append_to_map(embeddings, metadata, "Conversation Map for " + project['course_name'])
            if result == "success":
              last_id = int(final_df['id'].iloc[-1])
              project_info = {'last_uploaded_convo_id': last_id}
              project_response = self.sql.updateProjects(project['course_name'], project_info)
              print("Update response from supabase: ", project_response)

              # rebuild the map
              self.rebuild_map(project['course_name'], "conversation")

            else:
              print("Error in appending to existing map: ", result)

      return "success"
    
    except Exception as e:
      print("Error in update_conversation_maps():", e)
      self.sentry.capture_exception(e)
      return f"Error in updating conversation maps: {e}"
    

  def update_document_maps(self):
    """
    This function updates all document maps in UIUC.Chat. To be called via a CRON job.
    """
    try:
      # fetch all projects from SQL
      response = self.sql.getAllProjects()
      projects = response.data

      for project in projects:
        if not project['doc_map_id']:
          # need to create a new document map
          print("Creating new document map for course: ", project['course_name'])
          status = self.create_document_map(project['course_name'])
          print("Status of document map creation: ", status)
          
        else:
          print("Updating existing document map for course: ", project['course_name'])
          # check the last uploaded document id
          last_uploaded_doc_id = project['last_uploaded_doc_id']
          response = self.sql.getCountFromDocuments(project['course_name'], last_id=last_uploaded_doc_id)
          total_doc_count = response.count

          if total_doc_count == 0:
            print("No new documents to log.")
            continue
          else:
            print("Total number of unlogged documents in Supabase: ", total_doc_count)
            current_doc_count = 0
            combined_dfs = []
            while current_doc_count < total_doc_count:
              response = self.sql.getDocsForIdsGte(course_name=project['course_name'], first_id=last_uploaded_doc_id, limit=100)
              if len(response.data) == 0:
                break
              curr_df = pd.DataFrame(response.data)
              combined_dfs.append(curr_df)
              current_doc_count += len(response.data)

            # concat all dfs from the combined_dfs list
            final_df = pd.concat(combined_dfs, ignore_index=True)
            # prep data for nomic upload
            embeddings, metadata = self.data_prep_for_doc_map(final_df)

            # append to existing map
            print("Appending data to existing map...")
            result = self.append_to_map(embeddings, metadata, "Document Map for " + project['course_name'])
            if result == "success":
              last_id = int(final_df['id'].iloc[-1])
              project_info = {'last_uploaded_doc_id': last_id}
              project_response = self.sql.updateProjects(project['course_name'], project_info)
              print("Update response from supabase: ", project_response)

              # rebuild the map
              self.rebuild_map(project['course_name'], "document")

            else:
              print("Error in appending to existing map: ", result)

      return "success"
    
    except Exception as e:
      print("Error in update_document_maps", e)


  def create_conversation_map(self, course_name: str):
    """
    This function creates a conversation map for a given course from scratch.
    """
    nomic.login(os.getenv('NOMIC_API_KEY'))
    NOMIC_MAP_NAME_PREFIX = 'Conversation Map for '
    try:
      # check if map exists
      # response = self.sql.getConvoMapFromProjects(course_name)
      # print("Response from supabase: ", response.data)
      # if response.data:
      #   if response.data[0]['convo_map_id']:
      #     return "Map already exists for this course."

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
            result = self.create_map(metadata, project_name, index_name, index_field="first_query")
            
            if result == "success":
              # update flag
              first_batch = False
              # log project info to supabase
              project_name = project_name.replace(" ", "-").lower() 
              print("Project name: ", project_name)
              project = AtlasDataset(project_name)
              project_id = project.id
              last_id = int(final_df['id'].iloc[-1])
              project_info = {'course_name': course_name, 'convo_map_id': project_id, 'last_uploaded_convo_id': last_id}
              print("Project info: ", project_info)
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
            project_name = project_name.replace(" ", "-").lower()
            project = AtlasDataset(project_name)
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
          result = self.create_map(metadata, project_name, index_name, index_field="first_query")
          print("result of create map: ", result)

        else:
          # append to map
          print("in map append")
          result = self.append_to_map(embeddings, metadata, project_name)
        
        if result == "success":
          print("last map append successful")
          last_id = int(final_df['id'].iloc[-1])
          project_name = project_name.replace(" ", "-").lower()
          project = AtlasDataset(project_name)
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
    
  def create_document_map(self, course_name: str):
    """
    This function creates a document map for a given course from scratch.
    """
    try:
      # do shit
      project_name = "Document Map for " + course_name

      # check if project exists
      response = self.sql.getDocMapFromProjects(course_name=course_name)
      if response.data[0]['doc_map_id']:
        return "Map already exists."
      
      response = self.sql.getCountFromDocuments(course_name, last_id=0)

      # if <20, return message that map cannot be created
      if not response.count:
        return "No documents found for this course."
      elif response.count < 20:
        return "Cannot create a map because there are less than 20 documents in the course."

      # if >20, iteratively fetch records in batches of 100
      total_doc_count = response.count
      print("Total number of conversations in Supabase: ", total_doc_count)

      first_id = response.data[0]['id'] - 1
      combined_dfs = []
      current_doc_count = 0
      doc_count = 0
      first_batch = True

      while current_doc_count < total_doc_count:
        response = self.sql.getDocsForIdsGte(course_name=course_name, first_id=first_id, limit=100)
        print("Response count: ", len(response.data))
        if len(response.data) == 0:
          break
        df = pd.DataFrame(response.data)
        combined_dfs.append(df)
        current_doc_count += len(response.data)
        doc_count += len(response.data)
        print(current_doc_count)

        if doc_count >= 500:
          # concat all dfs from the combined_dfs list
          final_df = pd.concat(combined_dfs, ignore_index=True)
          # prep data for nomic upload
          embeddings, metadata = self.data_prep_for_doc_map(final_df)

          if first_batch:
            # create a new map
            print("Creating new map...")
            index_name = course_name + "_doc_index"
            
            result = self.create_map(metadata, project_name, index_name, index_field="text")
            
            if result == "success":
              # update flag
              first_batch = False
              # log project info to supabase
              project_name = project_name.replace(" ", "-").lower() 
              print("Project name: ", project_name)
              project = AtlasDataset(project_name)
              project_id = project.id
              last_id = int(final_df['id'].iloc[-1])
              project_info = {'course_name': course_name, 'doc_map_id': project_id, 'last_uploaded_doc_id': last_id}
              print("Project info: ", project_info)
              # if entry already exists, update it
              projects_record = self.sql.getDocMapFromProjects(course_name)
              if projects_record.data:
                project_response = self.sql.updateProjects(course_name, project_info)
              else:
                project_response = self.sql.insertProjectInfo(project_info)
              print("Update response from supabase: ", project_response)
          else:
            # append to existing map
            print("Appending data to existing map...")
            project_name = project_name.replace(" ", "-").lower()
            project = AtlasDataset(project_name)
            result = self.append_to_map(embeddings, metadata, project_name)
            if result == "success":
              print("map append successful")
              last_id = int(final_df['id'].iloc[-1])
              project_info = {'last_uploaded_doc_id': last_id}
              project_response = self.sql.updateProjects(course_name, project_info)
              print("Update response from supabase: ", project_response)

          # reset variables
          combined_dfs = []
          convo_count = 0
          print("Records uploaded: ", current_doc_count)

        # set first_id for next iteration
        try:
          print("response: ", response.data[-1]['id'])
        except:
          print("response: ", response.data)
        first_id = response.data[-1]['id'] + 1

      print("Convo count: ", doc_count)
      # upload last set of convos
      if doc_count > 0:
        print("Uploading last set of documents...")
        final_df = pd.concat(combined_dfs, ignore_index=True)
        embeddings, metadata = self.data_prep_for_doc_map(final_df)
        if first_batch:
          # create map
          index_name = course_name + "_doc_index"
          result = self.create_map(metadata, project_name, index_name, index_field="text")
          print("result of create map: ", result)

        else:
          # append to map
          print("in map append")
          result = self.append_to_map(embeddings, metadata, project_name)
        
        if result == "success":
          print("last map append successful")
          last_id = int(final_df['id'].iloc[-1])
          project_name = project_name.replace(" ", "-").lower()
          project = AtlasDataset(project_name)
          project_id = project.id
          project_info = {'course_name': course_name, 'doc_map_id': project_id, 'last_uploaded_doc_id': last_id}
          print("Project info: ", project_info)
          # if entry already exists, update it
          projects_record = self.sql.getDocMapFromProjects(course_name)
          if projects_record.data:
            project_response = self.sql.updateProjects(course_name, project_info)
          else:
            project_response = self.sql.insertProjectInfo(project_info)
          print("Response from supabase: ", project_response)


      # rebuild the map
      self.rebuild_map(course_name, "document")
      return "success"
      
    except Exception as e:
      print(e)
      self.sentry.capture_exception(e)
      return "Error in creating document map: " + str(e)


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
      project_name = project_name.replace(" ", "-").lower()
      project = AtlasDataset(project_name)

      if project.is_accepting_data:
        project.update_indices(rebuild_topic_models=True)
      return "success"
    except Exception as e:
      print(e)
      self.sentry.capture_exception(e)
      return "Error in rebuilding map: {e}"

  def create_map(self, metadata, map_name, index_name, index_field):
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
    # nomic.login(os.environ['NOMIC_API_KEY'])
    print("in create_map() for map name: ", map_name)
    try:
      # project = atlas.map_embeddings(embeddings=embeddings,
      #                                data=metadata,
      #                                id_field="id",
      #                                build_topic_model=True,
      #                                name=map_name,
      #                                topic_label_field=topic_label_field,
      #                                colorable_fields=colorable_fields,
      #                                add_datums_if_exists=True)
      #project = AtlasDataset(map_name, unique_id_field="id")
      project = atlas.map_data(data=metadata, 
                               identifier=map_name, 
                               id_field="id",
                               topic_model=True,
                               duplicate_detection=True,
                               indexed_field=index_field)
      project.create_index(name=index_name, 
                           indexed_field=index_field, 
                           topic_model=True, 
                           duplicate_detection=True)
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
      map_name = map_name.replace(" ", "-").lower()
      print("in append_to_map() for map name: ", map_name)
      project = AtlasDataset(map_name)
      if project.is_accepting_data:
        #project.add_data(embeddings=embeddings, data=metadata)
        project.add_data(data=metadata)
      else:
        print("Project is currently indexing and cannot ingest new datums. Try again later.")
      return "success"
    except Exception as e:
      print(e)
      return f"Error in appending to map: {e}"

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

        # some conversations include images, so the data structure is different
        if isinstance(messages[0]['content'], list):
          if 'text' in messages[0]['content'][0]:
            first_message = messages[0]['content'][0]['text']

        else:
          first_message = messages[0]['content']
        user_queries.append(first_message)

        # construct metadata for multi-turn conversation
        for message in messages:
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
        
        metadata.append(meta_row)

      metadata = pd.DataFrame(metadata)
      embeddings = []
      print("Metadata shape:", metadata.shape)
      return embeddings, metadata

    except Exception as e:
      print("Error in data_prep_for_convo_map():", e)
      self.sentry.capture_exception(e)
      return None, None
    

  def data_prep_for_doc_map(self, df: pd.DataFrame):
    """
    This function prepares metadata for nomic upload in document map creation.
    """
    try:
      metadata = []
      embeddings = []
      

      for index, row in df.iterrows():
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        created_at = datetime.datetime.strptime(row['created_at'], "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%Y-%m-%d %H:%M:%S")
        if row['url'] == None:
            row['url'] = ""
        if row['base_url'] == None:
            row['base_url'] = ""
        # iterate through all contexts and create separate entries for each
        context_count = 0
        for context in row['contexts']:
            context_count += 1
            text_row = context['text']
        
        meta_row = {
          "id": str(row['id']) + "_" + str(context_count),
          "created_at": created_at,
          "s3_path": row['s3_path'],
          "url": row['url'],
          "base_url": row['base_url'],  
          "readable_filename": row['readable_filename'],
          "modified_at": current_time,
          "text": text_row
        }

        metadata.append(meta_row)
      
      metadata = pd.DataFrame(metadata)
      embeddings = []

      return embeddings, metadata

    except Exception as e:
      print("Error in data_prep_for_doc_map():", e)
      self.sentry.capture_exception(e)
      return None, None


  def delete_from_document_map(self, course_name: str, ids: list):
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
      project_name = "Document Map for " + course_name
      project_name = project_name.replace(" ", "-").lower()
      project = AtlasDataset(project_name)

      # delete the ids from Nomic
      print("Deleting point from document map:", project.delete_data(ids))
      with project.wait_for_dataset_lock():
        project.update_indices(rebuild_topic_models=True)
      return "Successfully deleted from Nomic map"
    except Exception as e:
      print(e)
      self.sentry.capture_exception(e)
      return "Error in deleting from document map: {e}"
