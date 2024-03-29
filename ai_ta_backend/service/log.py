  @backoff.on_exception(backoff_strategy,
                        Exception,
                        max_tries=5,
                        raise_on_giveup=False,
                        giveup=giveup_hdlr,
                        on_backoff=backoff_hdlr)
  def log_convo_to_nomic(self, course_name: str, conversation) -> Union[str, None]:
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
      embeddings_model = OpenAIEmbeddings(openai_api_type=os.environ['OPENAI_API_TYPE'])
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