# import datetime
# import os

# import nomic
# import numpy as np
# import pandas as pd
# import sentry_sdk
# import supabase
# from langchain.embeddings import OpenAIEmbeddings
# from nomic import AtlasDataset, atlas

# OPENAI_API_TYPE = "azure"

# SUPABASE_CLIENT = supabase.create_client(  # type: ignore
#     supabase_url=os.getenv('SUPABASE_URL'),  # type: ignore
#     supabase_key=os.getenv('SUPABASE_API_KEY'))  # type: ignore

# NOMIC_MAP_NAME_PREFIX = 'Document Map for '
# nomic.login(os.getenv('NOMIC_API_KEY'))


# ## -------------------------------- DOCUMENT MAP FUNCTIONS --------------------------------- ##

# def create_document_map(course_name: str):
#   """
#   This is a function which creates a document map for a given course from scratch
#     1. Gets count of documents for the course
#     2. If less than 20, returns a message that a map cannot be created
#     3. If greater than 20, iteratively fetches documents in batches of 25
#     4. Prepares metadata and embeddings for nomic upload
#     5. Creates a new map and uploads the data

#   Args:
#     course_name: str
#   Returns:
#     str: success or failed
#   """
#   print("in create_document_map()")
 
#   try:
#     # check if map exists
#     response = SUPABASE_CLIENT.table("projects").select("doc_map_id").eq("course_name", course_name).execute()
#     if response.data:
#       if response.data[0]['doc_map_id']:
#         return "Map already exists for this course."

#     # fetch relevant document data from Supabase
#     response = SUPABASE_CLIENT.table("documents").select("id",
#                                                          count="exact").eq("course_name",
#                                                                            course_name).order('id',
#                                                                                               desc=False).execute()
#     if not response.count:
#       return "No documents found for this course."
    
#     total_doc_count = response.count
#     print("Total number of documents in Supabase: ", total_doc_count)

#     # minimum 20 docs needed to create map
#     if total_doc_count < 20:
#       return "Cannot create a map because there are less than 20 documents in the course."

#     first_id = response.data[0]['id']
    
#     combined_dfs = []
#     curr_total_doc_count = 0
#     doc_count = 0
#     first_batch = True

#     # iteratively query in batches of 25
#     while curr_total_doc_count < total_doc_count:
      
#       response = SUPABASE_CLIENT.table("documents").select(
#             "id, created_at, s3_path, url, base_url, readable_filename, contexts").eq("course_name", course_name).gte(
#                 'id', first_id).order('id', desc=False).limit(25).execute()
#       df = pd.DataFrame(response.data)
#       combined_dfs.append(df)  # list of dfs

#       curr_total_doc_count += len(response.data)
#       doc_count += len(response.data)

#       if doc_count >= 1000:  # upload to Nomic in batches of 1000

#         # concat all dfs from the combined_dfs list
#         final_df = pd.concat(combined_dfs, ignore_index=True)

#         # prep data for nomic upload
#         embeddings, metadata = data_prep_for_doc_map(final_df)

#         if first_batch:
#           # create a new map
#           print("Creating new map...")
#           project_name = NOMIC_MAP_NAME_PREFIX + course_name
#           index_name = course_name + "_doc_index"
#           topic_label_field = "text"
#           colorable_fields = ["readable_filename", "text", "base_url", "created_at"]
#           result = create_map(embeddings, metadata, project_name, index_name, topic_label_field, colorable_fields)
          
#           if result == "success":
#             # update flag
#             first_batch = False
#             # log project info to supabase
#             project_name = project_name.replace(" ", "-").lower()
#             project = AtlasDataset(project_name)
#             project_id = project.id
#             last_id = int(final_df['id'].iloc[-1])
#             project_info = {'course_name': course_name, 'doc_map_id': project_id, 'last_uploaded_doc_id': last_id}
#             project_response = SUPABASE_CLIENT.table("projects").select("*").eq("course_name", course_name).execute()
#             if project_response.data:
#               update_response = SUPABASE_CLIENT.table("projects").update(project_info).eq("course_name", course_name).execute()
#               print("Response from supabase: ", update_response)
#             else:
#               insert_response = SUPABASE_CLIENT.table("projects").insert(project_info).execute()
#               print("Insert Response from supabase: ", insert_response)
            

#         else:
#           # append to existing map
#           print("Appending data to existing map...")
#           project_name = NOMIC_MAP_NAME_PREFIX + course_name
#           # add project lock logic here
#           result = append_to_map(embeddings, metadata, project_name)
#           if result == "success":
#             # update the last uploaded id in supabase
#             last_id = int(final_df['id'].iloc[-1])
#             info = {'last_uploaded_doc_id': last_id}
#             update_response = SUPABASE_CLIENT.table("projects").update(info).eq("course_name", course_name).execute()
#             print("Response from supabase: ", update_response)
        
#         # reset variables
#         combined_dfs = []
#         doc_count = 0
#         print("Records uploaded: ", curr_total_doc_count)

#       # set first_id for next iteration
#       first_id = response.data[-1]['id'] + 1

#     # upload last set of docs
#     if doc_count > 0:
#       final_df = pd.concat(combined_dfs, ignore_index=True)
#       embeddings, metadata = data_prep_for_doc_map(final_df)
#       project_name = NOMIC_MAP_NAME_PREFIX + course_name
#       if first_batch:
#         index_name = course_name + "_doc_index"
#         topic_label_field = "text"
#         colorable_fields = ["readable_filename", "text", "base_url", "created_at"]
#         result = create_map(embeddings, metadata, project_name, index_name, topic_label_field, colorable_fields)
#       else:
#         result = append_to_map(embeddings, metadata, project_name)

#       # update the last uploaded id in supabase
#       if result == "success":
#         # update the last uploaded id in supabase
#         last_id = int(final_df['id'].iloc[-1])
#         project_name = project_name.replace(" ", "-").lower()
#         project = AtlasDataset(project_name)
#         project_id = project.id
#         project_info = {'course_name': course_name, 'doc_map_id': project_id, 'last_uploaded_doc_id': last_id}
#         print("project_info: ", project_info)
#         project_response = SUPABASE_CLIENT.table("projects").select("*").eq("course_name", course_name).execute()
#         if project_response.data:
#           update_response = SUPABASE_CLIENT.table("projects").update(project_info).eq("course_name", course_name).execute()
#           print("Response from supabase: ", update_response)
#         else:
#           insert_response = SUPABASE_CLIENT.table("projects").insert(project_info).execute()
#           print("Insert Response from supabase: ", insert_response)
        
  
#     # rebuild the map
#     rebuild_map(course_name, "document")
    
#   except Exception as e:
#     print(e)
#     sentry_sdk.capture_exception(e)
#     return "failed"

# # def delete_from_document_map(course_name: str, ids: list):
# #   """
# #   This function is used to delete datapoints from a document map.
# #   Currently used within the delete_data() function in vector_database.py
# #   Args:
# #     course_name: str
# #     ids: list of str
# #   """
# #   print("in delete_from_document_map()")

# #   try:
# #     # check if project exists
# #     response = SUPABASE_CLIENT.table("projects").select("doc_map_id").eq("course_name", course_name).execute()
# #     if response.data:
# #       project_id = response.data[0]['doc_map_id']
# #     else:
# #       return "No document map found for this course"

# #     # fetch project from Nomic
# #     project = AtlasProject(project_id=project_id, add_datums_if_exists=True)

# #     # delete the ids from Nomic
# #     print("Deleting point from document map:", project.delete_data(ids))
# #     with project.wait_for_project_lock():
# #       project.rebuild_maps()
# #     return "success"
# #   except Exception as e:
# #     print(e)
# #     sentry_sdk.capture_exception(e)
# #     return "Error in deleting from document map: {e}"


# # def log_to_document_map(course_name: str):
# #   """
# #   This is a function which appends new documents to an existing document map. It's called 
# #   at the end of split_and_upload() after inserting data to Supabase.
# #   Args:
# #     data: dict - the response data from Supabase insertion
# #   """
# #   print("in add_to_document_map()")

# #   try:
# #   # check if map exists
# #     response = SUPABASE_CLIENT.table("projects").select("doc_map_id, last_uploaded_doc_id").eq("course_name", course_name).execute()
# #     if response.data:
# #       if response.data[0]['doc_map_id']:
# #         project_id = response.data[0]['doc_map_id']
# #         last_uploaded_doc_id = response.data[0]['last_uploaded_doc_id']
# #       else:
# #         # entry present in supabase, but doc map not present
# #         create_document_map(course_name)
# #         return "Document map not present, triggering map creation."

# #     else:
# #       # create a map
# #       create_document_map(course_name)
# #       return "Document map not present, triggering map creation."
      
# #     project = AtlasDataset(project_id=project_id, add_datums_if_exists=True)
# #     project_name = "Document Map for " + course_name
    
# #     # check if project is LOCKED, if yes -> skip logging
# #     if not project.is_accepting_data:
# #       return "Skipping Nomic logging because project is locked."
        
# #     # fetch count of records greater than last_uploaded_doc_id
# #     print("last uploaded doc id: ", last_uploaded_doc_id)
# #     response = SUPABASE_CLIENT.table("documents").select("id", count="exact").eq("course_name", course_name).gt("id", last_uploaded_doc_id).execute()
# #     print("Number of new documents: ", response.count)

# #     total_doc_count = response.count
# #     current_doc_count = 0
# #     combined_dfs = []
# #     doc_count = 0
# #     first_id = last_uploaded_doc_id
# #     while current_doc_count < total_doc_count:
# #       # fetch all records from supabase greater than last_uploaded_doc_id
# #       response = SUPABASE_CLIENT.table("documents").select("id, created_at, s3_path, url, base_url, readable_filename, contexts").eq("course_name", course_name).gt("id", first_id).limit(25).execute()
# #       df = pd.DataFrame(response.data)
# #       combined_dfs.append(df)  # list of dfs

# #       current_doc_count += len(response.data)
# #       doc_count += len(response.data)

# #       if doc_count >= 1000:  # upload to Nomic in batches of 1000
# #         # concat all dfs from the combined_dfs list
# #         final_df = pd.concat(combined_dfs, ignore_index=True)
# #         # prep data for nomic upload
# #         embeddings, metadata = data_prep_for_doc_map(final_df)

# #         # append to existing map
# #         print("Appending data to existing map...")
                               
# #         result = append_to_map(embeddings, metadata, project_name)
# #         if result == "success":
# #           # update the last uploaded id in supabase
# #           last_id = int(final_df['id'].iloc[-1])
# #           info = {'last_uploaded_doc_id': last_id}
# #           update_response = SUPABASE_CLIENT.table("projects").update(info).eq("course_name", course_name).execute()
# #           print("Response from supabase: ", update_response)
                
# #         # reset variables
# #         combined_dfs = []
# #         doc_count = 0
# #         print("Records uploaded: ", current_doc_count)
            
# #       # set first_id for next iteration
# #       first_id = response.data[-1]['id'] + 1
        
# #     # upload last set of docs
# #     if doc_count > 0:
# #       final_df = pd.concat(combined_dfs, ignore_index=True)
# #       embeddings, metadata = data_prep_for_doc_map(final_df)
# #       result = append_to_map(embeddings, metadata, project_name)

# #       # update the last uploaded id in supabase
# #       if result == "success":
# #         # update the last uploaded id in supabase
# #         last_id = int(final_df['id'].iloc[-1])
# #         project_info = {'last_uploaded_doc_id': last_id}
# #         update_response = SUPABASE_CLIENT.table("projects").update(project_info).eq("course_name", course_name).execute()
# #         print("Response from supabase: ", update_response)
            
# #     return "success"
# #   except Exception as e:
# #     print(e)
# #     return "failed"        
                
    
# def create_map(embeddings, metadata, map_name, index_name, topic_label_field, colorable_fields):
#   """
#   Generic function to create a Nomic map from given parameters.
#   Args:
#     embeddings: np.array of embeddings
#     metadata: pd.DataFrame of metadata
#     map_name: str
#     index_name: str
#     topic_label_field: str
#     colorable_fields: list of str
#   """
#   nomic.login(os.getenv('NOMIC_API_KEY'))
#   try:
#     # project = atlas.map_embeddings(embeddings=embeddings,
#     #                                data=metadata,
#     #                                id_field="id",
#     #                                build_topic_model=True,
#     #                                topic_label_field=topic_label_field,
#     #                                name=map_name,
#     #                                colorable_fields=colorable_fields,
#     #                                add_datums_if_exists=True)
#     # project.create_index(name=index_name, build_topic_model=True)

#     project = atlas.map_data(data=metadata,
#                              id_field="id",
#                              topic_model=True,
#                              identifier=map_name,
#                              duplicate_detection=True,
#                              indexed_field=index_name)
#     project.create_index(name=index_name, topic_model=True, duplicate_detection=True)

#     return "success"
#   except Exception as e:
#     print(e)
#     return "Error in creating map: {e}"

# def append_to_map(embeddings, metadata, map_name):
#   """
#   Generic function to append new data to an existing Nomic map.
#   Args:
#     embeddings: np.array of embeddings
#     metadata: pd.DataFrame of Nomic upload metadata
#     map_name: str
#   """
#   try:
#     map_name = map_name.replace(" ", "-").lower()
#     project = AtlasDataset(identifier=map_name)
#     if project.is_accepting_data:
#       project.add_data(data=metadata)
#     return "success"
#   except Exception as e:
#     print(e)
#     return "Error in appending to map: {e}"

# def data_prep_for_doc_map(df: pd.DataFrame):
#   """
#   This function prepares embeddings and metadata for nomic upload in document map creation.
#     Args:
#         df: pd.DataFrame - the dataframe of documents from Supabase
#     Returns:
#         embeddings: np.array of embeddings
#         metadata: pd.DataFrame of metadata
#     """
#     print("in data_prep_for_doc_map()")

#     metadata = []
#     embeddings = []

#     texts = []

#     for index, row in df.iterrows():
#       current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#       created_at = datetime.datetime.strptime(row['created_at'], "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%Y-%m-%d %H:%M:%S")
#       if row['url'] == None:
#         row['url'] = ""
#       if row['base_url'] == None:
#         row['base_url'] = ""
#       # iterate through all contexts and create separate entries for each
#       context_count = 0
#       for context in row['contexts']:
#         context_count += 1
#         text_row = context['text']
#         embeddings_row = context['embedding']

#       meta_row = {
#         "id": str(row['id']) + "_" + str(context_count),
#         "created_at": created_at,
#         "s3_path": row['s3_path'],
#         "url": row['url'],
#         "base_url": row['base_url'],  
#         "readable_filename": row['readable_filename'],
#         "modified_at": current_time,
#         "text": text_row
#       }

#       embeddings.append(embeddings_row)
#       metadata.append(meta_row)
#       texts.append(text_row)

#     embeddings_np = np.array(embeddings, dtype=object)
#     print("Shape of embeddings: ", embeddings_np.shape)

#     # check dimension if embeddings_np is (n, 1536)
#     # if len(embeddings_np.shape) < 2:
#     #     print("Creating new embeddings...")

#     #     embeddings_model = OpenAIEmbeddings(openai_api_type="openai",
#     #                                         openai_api_base="https://api.openai.com/v1/",
#     #                                         openai_api_key=os.getenv('VLADS_OPENAI_KEY'))  # type: ignore
#     #     embeddings = embeddings_model.embed_documents(texts)

#     metadata = pd.DataFrame(metadata)
#     embeddings = np.array(embeddings)

#     return embeddings, metadata

# def rebuild_map(course_name:str, map_type:str):
#     """
#     This function rebuilds a given map in Nomic.
#     """
#     print("in rebuild_map()")
#     nomic.login(os.getenv('NOMIC_API_KEY'))
#     if map_type.lower() == 'document':
#         NOMIC_MAP_NAME_PREFIX = 'Document Map for '
#     else:
#         NOMIC_MAP_NAME_PREFIX = 'Conversation Map for '

#     try:
#         # fetch project from Nomic
#         project_name = NOMIC_MAP_NAME_PREFIX + course_name
#         project_name = project_name.replace(" ", "-").lower()
#         project = AtlasDataset(project_name)

#         if project.is_accepting_data: # temporary fix - will skip rebuilding if project is locked
#             project.update_indices()
#         return "success"
#     except Exception as e:
#         print(e)
#         sentry_sdk.capture_exception(e)
#         return f"Error in rebuilding map: {e}"



# if __name__ == '__main__':
#   pass

