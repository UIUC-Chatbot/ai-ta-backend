import datetime
import os
import time

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
    nomic.login(os.getenv('NOMIC_API_KEY'))
    self.sentry = sentry
    self.sql = sql

  @backoff.on_exception(backoff_strategy,
                        Exception,
                        max_tries=5,
                        raise_on_giveup=False,
                        giveup=giveup_hdlr,
                        on_backoff=backoff_hdlr)
  def log_convo_to_nomic(self, course_name: str, conversation) -> str | None:
    # nomic.login(os.getenv('NOMIC_API_KEY'))  # login during start of flask app
    NOMIC_MAP_NAME_PREFIX = 'Conversation Map for '
    """
			Logs conversation to Nomic.
			1. Check if map exists for given course
			2. Check if conversation ID exists 
					- if yes, delete and add new data point
					- if no, add new data point
			3. Keep current logic for map doesn't exist - update metadata
			"""

    print(f"in log_convo_to_nomic() for course: {course_name}")
    print("type of conversation:", type(conversation))
    #conversation = json.loads(conversation)
    messages = conversation['conversation']['messages']
    if 'user_email' not in conversation['conversation']:
      user_email = "NULL"
    else:
      user_email = conversation['conversation']['user_email']
    conversation_id = conversation['conversation']['id']

    # we have to upload whole conversations
    # check what the fetched data looks like - pandas df or pyarrow table
    # check if conversation ID exists in Nomic, if yes fetch all data from it and delete it.
    # will have current QA and historical QA from Nomic, append new data and add_embeddings()

    project_name = NOMIC_MAP_NAME_PREFIX + course_name
    start_time = time.monotonic()
    emoji = ""

    try:
      # fetch project metadata and embbeddings
      project = AtlasProject(name=project_name, add_datums_if_exists=True)

      map_metadata_df = project.maps[1].data.df  # type: ignore
      map_embeddings_df = project.maps[1].embeddings.latent
      # create a function which returns project, data and embeddings df here
      map_metadata_df['id'] = map_metadata_df['id'].astype(int)
      last_id = map_metadata_df['id'].max()

      if conversation_id in map_metadata_df.values:
        # store that convo metadata locally
        prev_data = map_metadata_df[map_metadata_df['conversation_id'] == conversation_id]
        prev_index = prev_data.index.values[0]
        embeddings = map_embeddings_df[prev_index - 1].reshape(1, 1536)
        prev_convo = prev_data['conversation'].values[0]
        prev_id = prev_data['id'].values[0]
        created_at = pd.to_datetime(prev_data['created_at'].values[0]).strftime('%Y-%m-%d %H:%M:%S')

        # delete that convo data point from Nomic, and print result
        print("Deleting point from nomic:", project.delete_data([str(prev_id)]))

        # prep for new point
        first_message = prev_convo.split("\n")[1].split(": ")[1]

        # select the last 2 messages and append new convo to prev convo
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

        # modified timestamp
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # update metadata
        metadata = [{
            "course": course_name,
            "conversation": prev_convo,
            "conversation_id": conversation_id,
            "id": last_id + 1,
            "user_email": user_email,
            "first_query": first_message,
            "created_at": created_at,
            "modified_at": current_time
        }]
      else:
        print("conversation_id does not exist")

        # add new data point
        user_queries = []
        conversation_string = ""

        first_message = messages[0]['content']
        if isinstance(first_message, list):
          first_message = first_message[0]['text']
        user_queries.append(first_message)

        for message in messages:
          if message['role'] == 'user':
            emoji = "🙋 "
          else:
            emoji = "🤖 "

          if isinstance(message['content'], list):
            text = message['content'][0]['text']
          else:
            text = message['content']

          conversation_string += "\n>>> " + emoji + message['role'] + ": " + text + "\n"

        # modified timestamp
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        metadata = [{
            "course": course_name,
            "conversation": conversation_string,
            "conversation_id": conversation_id,
            "id": last_id + 1,
            "user_email": user_email,
            "first_query": first_message,
            "created_at": current_time,
            "modified_at": current_time
        }]

        # create embeddings
        embeddings_model = OpenAIEmbeddings(openai_api_type=OPENAI_API_TYPE)  # type: ignore
        embeddings = embeddings_model.embed_documents(user_queries)

      # add embeddings to the project - create a new function for this
      project = atlas.AtlasProject(name=project_name, add_datums_if_exists=True)
      with project.wait_for_project_lock():
        project.add_embeddings(embeddings=np.array(embeddings), data=pd.DataFrame(metadata))
        project.rebuild_maps()

      print(f"⏰ Nomic logging runtime: {(time.monotonic() - start_time):.2f} seconds")
      return f"Successfully logged for {course_name}"

    except Exception as e:
      if str(e) == 'You must specify a unique_id_field when creating a new project.':
        print("Attempting to create Nomic map...")
        result = self.create_nomic_map(course_name, conversation)
        print("result of create_nomic_map():", result)
      else:
        # raising exception again to trigger backoff and passing parameters to use in create_nomic_map()
        raise Exception({"exception": str(e)})

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

  def create_nomic_map(self, course_name: str, log_data: list):
    """
		Creates a Nomic map for new courses and those which previously had < 20 queries.
		1. fetches supabase conversations for course
		2. appends current embeddings and metadata to it
		2. creates map if there are at least 20 queries
		"""
    nomic.login(os.getenv('NOMIC_API_KEY'))  # login during start of flask app
    NOMIC_MAP_NAME_PREFIX = 'Conversation Map for '

    print(f"in create_nomic_map() for {course_name}")
    # initialize supabase
    supabase_client = supabase.create_client(  # type: ignore
        supabase_url=os.getenv('SUPABASE_URL'),  # type: ignore
        supabase_key=os.getenv('SUPABASE_API_KEY'))  # type: ignore

    try:
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
        log_messages = log_data['conversation']['messages']  # type: ignore
        log_user_email = log_data['conversation']['user_email']  # type: ignore
        log_conversation_id = log_data['conversation']['id']  # type: ignore

        for _index, row in df.iterrows():
          user_email = row['user_email']
          created_at = pd.to_datetime(row['created_at']).strftime('%Y-%m-%d %H:%M:%S')
          convo = row['convo']
          messages = convo['messages']

          first_message = messages[0]['content']
          if isinstance(first_message, list):
            first_message = first_message[0]['text']

          user_queries.append(first_message)

          # create metadata for multi-turn conversation
          conversation = ""
          for message in messages:
            # string of role: content, role: content, ...
            if message['role'] == 'user':  # type: ignore
              emoji = "🙋 "
            else:
              emoji = "🤖 "

            if isinstance(message['content'], list):
              text = message['content'][0]['text']
            else:
              text = message['content']

            conversation += "\n>>> " + emoji + message['role'] + ": " + text + "\n"

          # append current chat to previous chat if convo already exists
          if convo['id'] == log_conversation_id:
            conversation_exists = True

            for m in log_messages:
              if m['role'] == 'user':  # type: ignore
                emoji = "🙋 "
              else:
                emoji = "🤖 "

              if isinstance(m['content'], list):
                text = m['content'][0]['text']
              else:
                text = m['content']
              conversation += "\n>>> " + emoji + m['role'] + ": " + text + "\n"

          # adding modified timestamp
          current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

          # add to metadata
          metadata_row = {
              "course": row['course_name'],
              "conversation": conversation,
              "conversation_id": convo['id'],
              "id": i,
              "user_email": user_email,
              "first_query": first_message,
              "created_at": created_at,
              "modified_at": current_time
          }
          metadata.append(metadata_row)
          i += 1

        # add current log as a new data point if convo doesn't exist
        if not conversation_exists:
          user_queries.append(log_messages[0]['content'])
          conversation = ""
          for message in log_messages:
            if message['role'] == 'user':
              emoji = "🙋 "
            else:
              emoji = "🤖 "

            if isinstance(message['content'], list):
              text = message['content'][0]['text']
            else:
              text = message['content']
            conversation += "\n>>> " + emoji + message['role'] + ": " + text + "\n"

          # adding timestamp
          current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

          metadata_row = {
              "course": course_name,
              "conversation": conversation,
              "conversation_id": log_conversation_id,
              "id": i,
              "user_email": log_user_email,
              "first_query": log_messages[0]['content'],
              "created_at": current_time,
              "modified_at": current_time
          }
          metadata.append(metadata_row)

        metadata = pd.DataFrame(metadata)
        embeddings_model = OpenAIEmbeddings(openai_api_type=OPENAI_API_TYPE)  # type: ignore
        embeddings = embeddings_model.embed_documents(user_queries)

        # create Atlas project
        project_name = NOMIC_MAP_NAME_PREFIX + course_name
        index_name = course_name + "_convo_index"
        project = atlas.map_embeddings(
            embeddings=np.array(embeddings),
            data=metadata,  # type: ignore - this is the correct type, the func signature from Nomic is incomplete
            id_field='id',
            build_topic_model=True,
            topic_label_field='first_query',
            name=project_name,
            colorable_fields=['conversation_id', 'first_query'])
        project.create_index(index_name, build_topic_model=True)
        return f"Successfully created Nomic map for {course_name}"
    except Exception as e:
      # Error: ValueError: You must specify a unique_id_field when creating a new project.
      if str(e) == 'You must specify a unique_id_field when creating a new project.':  # type: ignore
        print("Nomic map does not exist yet, probably because you have less than 20 queries on your project: ", e)
      else:
        print("ERROR in create_nomic_map():", e)
        self.sentry.capture_exception(e)

      return "failed"

  ## -------------------------------- DOCUMENT MAP FUNCTIONS --------------------------------- ##

  def create_document_map(self, course_name: str):
    """
		This is a function which creates a document map for a given course from scratch
			1. Gets count of documents for the course
			2. If less than 20, returns a message that a map cannot be created
			3. If greater than 20, iteratively fetches documents in batches of 25
			4. Prepares metadata and embeddings for nomic upload
			5. Creates a new map and uploads the data

		Args:
			course_name: str
		Returns:
			str: success or failed
		"""
    print("in create_document_map()")
    # nomic.login(os.getenv('NOMIC_API_KEY'))
    NOMIC_MAP_NAME_PREFIX = 'Document Map for '

    try:
      # check if map exists

      response = self.sql.getProjectsMapForCourse(course_name)
      if response.data:
        return "Map already exists for this course."

      # fetch relevant document data from Supabase
      response = self.sql.getDocumentsBetweenDates(course_name, '', '', "documents")

      if not response.count:
        return "No documents found for this course."

      total_doc_count = response.count
      print("Total number of documents in Supabase: ", total_doc_count)

      # minimum 20 docs needed to create map
      if total_doc_count > 19:

        first_id = response.data[0]['id']
        combined_dfs = []
        curr_total_doc_count = 0
        doc_count = 0
        first_batch = True

        # iteratively query in batches of 25
        while curr_total_doc_count < total_doc_count:

          response = self.sql.getDocsForIdsGte(course_name, first_id,
                                               "id, created_at, s3_path, url, readable_filename, contexts", 25)

          df = pd.DataFrame(response.data)
          combined_dfs.append(df)  # list of dfs

          curr_total_doc_count += len(response.data)
          doc_count += len(response.data)

          if doc_count >= 1000:  # upload to Nomic every 1000 docs

            # concat all dfs from the combined_dfs list
            final_df = pd.concat(combined_dfs, ignore_index=True)

            # prep data for nomic upload
            embeddings, metadata = self.data_prep_for_doc_map(final_df)

            if first_batch:
              # create a new map
              print("Creating new map...")
              project_name = NOMIC_MAP_NAME_PREFIX + course_name
              index_name = course_name + "_doc_index"
              topic_label_field = "text"
              colorable_fields = ["readable_filename", "text"]
              result = self.create_map(embeddings, metadata, project_name, index_name, topic_label_field,
                                       colorable_fields)
              # update flag
              first_batch = False

            else:
              # append to existing map
              print("Appending data to existing map...")
              project_name = NOMIC_MAP_NAME_PREFIX + course_name
              # add project lock logic here
              result = self.append_to_map(embeddings, metadata, project_name)

            # reset variables
            combined_dfs = []
            doc_count = 0

          # set first_id for next iteration
          first_id = response.data[-1]['id'] + 1

        # upload last set of docs
        final_df = pd.concat(combined_dfs, ignore_index=True)
        embeddings, metadata = self.data_prep_for_doc_map(final_df)
        project_name = NOMIC_MAP_NAME_PREFIX + course_name
        if first_batch:
          index_name = course_name + "_doc_index"
          topic_label_field = "text"
          colorable_fields = ["readable_filename", "text"]
          result = self.create_map(embeddings, metadata, project_name, index_name, topic_label_field, colorable_fields)
        else:
          result = self.append_to_map(embeddings, metadata, project_name)
        print("Atlas upload status: ", result)

        # log info to supabase
        project = AtlasProject(name=project_name, add_datums_if_exists=True)
        project_id = project.id
        project.rebuild_maps()
        project_info = {'course_name': course_name, 'doc_map_id': project_id}
        response = self.sql.insertProjectInfo(project_info)
        print("Response from supabase: ", response)
        return "success"
      else:
        return "Cannot create a map because there are less than 20 documents in the course."
    except Exception as e:
      print(e)
      self.sentry.capture_exception(e)
      return "failed"

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

  # If this needs to be uncommented, make sure to move the supabase call to the respective service
  # def log_to_document_map(self, data: dict):
  # 	"""
  # 	This is a function which appends new documents to an existing document map. It's called
  # 	at the end of split_and_upload() after inserting data to Supabase.
  # 	Args:
  # 		data: dict - the response data from Supabase insertion
  # 	"""
  # 	print("in add_to_document_map()")

  # 	try:
  # 		# check if map exists
  # 		course_name = data['course_name']
  # 		response = SUPABASE_CLIENT.table("projects").select("doc_map_id").eq("course_name", course_name).execute()
  # 		if response.data:
  # 			project_id = response.data[0]['doc_map_id']
  # 		else:
  # 			# create a map
  # 			map_creation_result = self.create_document_map(course_name)
  # 			if map_creation_result != "success":
  # 				return "The project has less than 20 documents and a map cannot be created."
  # 			else:
  # 				# fetch project id
  # 				response = SUPABASE_CLIENT.table("projects").select("doc_map_id").eq("course_name", course_name).execute()
  # 				project_id = response.data[0]['doc_map_id']

  # 		project = AtlasProject(project_id=project_id, add_datums_if_exists=True)
  # 		#print("Inserted data: ", data)

  # 		embeddings = []
  # 		metadata = []
  # 		context_count = 0
  # 		# prep data for nomic upload
  # 		for row in data['contexts']:
  # 			context_count += 1
  # 			embeddings.append(row['embedding'])
  # 			metadata.append({
  # 				"id": str(data['id']) + "_" + str(context_count),
  # 				"doc_ingested_at": data['created_at'],
  # 				"s3_path": data['s3_path'],
  # 				"url": data['url'],
  # 				"readable_filename": data['readable_filename'],
  # 				"created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
  # 				"text": row['text']
  # 			})
  # 		embeddings = np.array(embeddings)
  # 		metadata = pd.DataFrame(metadata)
  # 		print("Shape of embeddings: ", embeddings.shape)

  # 		# append to existing map
  # 		project_name = "Document Map for " + course_name
  # 		result = self.append_to_map(embeddings, metadata, project_name)

  # 		# check if project is accepting new datums
  # 		if project.is_accepting_data:
  # 			with project.wait_for_project_lock():
  # 				project.rebuild_maps()

  # 		# with project.wait_for_project_lock():
  # 		#   project.rebuild_maps()
  # 		return result

  # 	except Exception as e:
  # 		print(e)
  # 		self.sentry.capture_exception(e)
  # 		return "Error in appending to map: {e}"

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
    nomic.login(os.getenv('NOMIC_API_KEY'))

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
    nomic.login(os.getenv('NOMIC_API_KEY'))
    try:
      project = atlas.AtlasProject(name=map_name, add_datums_if_exists=True)
      with project.wait_for_project_lock():
        project.add_embeddings(embeddings=embeddings, data=metadata)
      return "Successfully appended to Nomic map"
    except Exception as e:
      print(e)
      return "Error in appending to map: {e}"

  def data_prep_for_doc_map(self, df: pd.DataFrame):
    """
		This function prepares embeddings and metadata for nomic upload in document map creation.
		Args:
			df: pd.DataFrame - the dataframe of documents from Supabase
		Returns:
			embeddings: np.array of embeddings
			metadata: pd.DataFrame of metadata
		"""
    print("in data_prep_for_doc_map()")

    metadata = []
    embeddings = []
    texts = []

    for index, row in df.iterrows():

      current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      if row['url'] == None:
        row['url'] = ""
      # iterate through all contexts and create separate entries for each
      context_count = 0
      for context in row['contexts']:
        context_count += 1
        text_row = context['text']
        embeddings_row = context['embedding']

        meta_row = {
            "id": str(row['id']) + "_" + str(context_count),
            "doc_ingested_at": row['created_at'],
            "s3_path": row['s3_path'],
            "url": row['url'],
            "readable_filename": row['readable_filename'],
            "created_at": current_time,
            "text": text_row
        }

        embeddings.append(embeddings_row)
        metadata.append(meta_row)
        texts.append(text_row)

    embeddings_np = np.array(embeddings, dtype=object)
    print("Shape of embeddings: ", embeddings_np.shape)

    # check dimension if embeddings_np is (n, 1536)
    if len(embeddings_np.shape) < 2:
      print("Creating new embeddings...")
      # embeddings_model = OpenAIEmbeddings(openai_api_type=OPENAI_API_TYPE,
      #                                     openai_api_base=os.getenv('AZURE_OPENAI_BASE'),
      #                                     openai_api_key=os.getenv('AZURE_OPENAI_KEY')) # type: ignore
      embeddings_model = OpenAIEmbeddings(openai_api_type="openai",
                                          openai_api_base="https://api.openai.com/v1/",
                                          openai_api_key=os.getenv('VLADS_OPENAI_KEY'))  # type: ignore
      embeddings = embeddings_model.embed_documents(texts)

    metadata = pd.DataFrame(metadata)
    embeddings = np.array(embeddings)

    return embeddings, metadata
