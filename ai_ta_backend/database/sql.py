import os
from typing import Dict

from injector import inject

import supabase


class SQLDatabase:

  @inject
  def __init__(self):
    # Create a Supabase client
    self.supabase_client = supabase.create_client(  # type: ignore
        supabase_url=os.environ['SUPABASE_URL'], supabase_key=os.environ['SUPABASE_API_KEY'])

  def getAllMaterialsForCourse(self, course_name: str):
    return self.supabase_client.table(
        os.environ['SUPABASE_DOCUMENTS_TABLE']).select('course_name, s3_path, readable_filename, url, base_url').eq(
            'course_name', course_name).execute()

  def getMaterialsForCourseAndS3Path(self, course_name: str, s3_path: str):
    return self.supabase_client.from_(os.environ['SUPABASE_DOCUMENTS_TABLE']).select("id, s3_path, contexts").eq(
        's3_path', s3_path).eq('course_name', course_name).execute()

  def getMaterialsForCourseAndKeyAndValue(self, course_name: str, key: str, value: str):
    return self.supabase_client.from_(os.environ['SUPABASE_DOCUMENTS_TABLE']).select("id, s3_path, contexts").eq(
        key, value).eq('course_name', course_name).execute()

  def deleteMaterialsForCourseAndKeyAndValue(self, course_name: str, key: str, value: str):
    return self.supabase_client.from_(os.environ['SUPABASE_DOCUMENTS_TABLE']).delete().eq(key, value).eq(
        'course_name', course_name).execute()

  def deleteMaterialsForCourseAndS3Path(self, course_name: str, s3_path: str):
    return self.supabase_client.from_(os.environ['SUPABASE_DOCUMENTS_TABLE']).delete().eq('s3_path', s3_path).eq(
        'course_name', course_name).execute()

  def getProjectsMapForCourse(self, course_name: str):
    return self.supabase_client.table("projects").select("doc_map_id").eq("course_name", course_name).execute()

  def getDocumentsBetweenDates(self, course_name: str, from_date: str, to_date: str, table_name: str):
    if from_date != '' and to_date != '':
      # query between the dates
      print("from_date and to_date")

      response = self.supabase_client.table(table_name).select("id", count='exact').eq("course_name", course_name).gte(
          'created_at', from_date).lte('created_at', to_date).order('id', desc=False).execute()

    elif from_date != '' and to_date == '':
      # query from from_date to now
      print("only from_date")
      response = self.supabase_client.table(table_name).select("id", count='exact').eq("course_name", course_name).gte(
          'created_at', from_date).order('id', desc=False).execute()

    elif from_date == '' and to_date != '':
      # query from beginning to to_date
      print("only to_date")
      response = self.supabase_client.table(table_name).select("id", count='exact').eq("course_name", course_name).lte(
          'created_at', to_date).order('id', desc=False).execute()

    else:
      # query all data
      print("No dates")
      response = self.supabase_client.table(table_name).select("id", count='exact').eq(
          "course_name", course_name).order('id', desc=False).execute()
    return response

  def getAllFromTableForDownloadType(self, course_name: str, download_type: str, first_id: int):
    if download_type == 'documents':
      response = self.supabase_client.table("documents").select("*").eq("course_name", course_name).gte(
          'id', first_id).order('id', desc=False).limit(100).execute()
    else:
      response = self.supabase_client.table("llm-convo-monitor").select("*").eq("course_name", course_name).gte(
          'id', first_id).order('id', desc=False).limit(100).execute()

    return response

  def getAllConversationsBetweenIds(self, course_name: str, first_id: int, last_id: int, limit: int = 50):
    if last_id == 0:
      return self.supabase_client.table("llm-convo-monitor").select("*").eq("course_name", course_name).gt(
          'id', first_id).order('id', desc=False).limit(limit).execute()
    else:
      return self.supabase_client.table("llm-convo-monitor").select("*").eq("course_name", course_name).gte(
          'id', first_id).lte('id', last_id).order('id', desc=False).limit(limit).execute()

  def getDocsForIdsGte(self, course_name: str, first_id: int, fields: str = "*", limit: int = 100):
    return self.supabase_client.table("documents").select(fields).eq("course_name", course_name).gte(
        'id', first_id).order('id', desc=False).limit(limit).execute()

  def insertProjectInfo(self, project_info):
    return self.supabase_client.table("projects").insert(project_info).execute()

  def getAllFromLLMConvoMonitor(self, course_name: str):
    return self.supabase_client.table("llm-convo-monitor").select("*").eq("course_name",
                                                                          course_name).order('id',
                                                                                             desc=False).execute()

  def getCountFromLLMConvoMonitor(self, course_name: str, last_id: int):
    if last_id == 0:
      return self.supabase_client.table("llm-convo-monitor").select("id", count='exact').eq(
          "course_name", course_name).order('id', desc=False).execute()
    else:
      return self.supabase_client.table("llm-convo-monitor").select("id", count='exact').eq(
          "course_name", course_name).gt("id", last_id).order('id', desc=False).execute()

  def getCountFromDocuments(self, course_name: str, last_id: int):
    if last_id == 0:
      return self.supabase_client.table("documents").select("id", count='exact').eq("course_name",
        course_name).order('id', desc=False).execute()
    else:
      return self.supabase_client.table("documents").select("id", count='exact').eq("course_name",
        course_name).gt("id", last_id).order('id', desc=False).execute()
                                                                                                            
  def getDocMapFromProjects(self, course_name: str):
    return self.supabase_client.table("projects").select("doc_map_id").eq("course_name", course_name).execute()

  def getConvoMapFromProjects(self, course_name: str):
    return self.supabase_client.table("projects").select("*").eq("course_name", course_name).execute()

  def updateProjects(self, course_name: str, data: dict):
    return self.supabase_client.table("projects").update(data).eq("course_name", course_name).execute()

  def getLatestWorkflowId(self):
    return self.supabase_client.table('n8n_workflows').select("*").execute()

  def lockWorkflow(self, id: int):
    return self.supabase_client.table('n8n_workflows').insert({"latest_workflow_id": id, "is_locked": True}).execute()
    # return self.supabase_client.table('n8n_workflows').update({"latest_workflow_id":id, "is_locked": True}).eq('latest_workflow_id', supabase_id).execute()

  def deleteLatestWorkflowId(self, id: int):
    return self.supabase_client.table('n8n_workflows').delete().eq('latest_workflow_id', id).execute()

  def unlockWorkflow(self, id: int):
    return self.supabase_client.table('n8n_workflows').update({
        "is_locked": False
    }).eq('latest_workflow_id', id).execute()

  def check_and_lock_flow(self, id):
    return self.supabase_client.rpc('check_and_lock_flows_v2', {'id': id}).execute()

  def getConversation(self, course_name: str, key: str, value: str):
    return self.supabase_client.table("llm-convo-monitor").select("*").eq(key, value).eq("course_name",
                                                                                         course_name).execute()

  def getDisabledDocGroups(self, course_name: str):
    return self.supabase_client.table("doc_groups").select("name").eq("course_name", course_name).eq("enabled",
                                                                                                     False).execute()

  def getPublicDocGroups(self, course_name: str):
    return self.supabase_client.from_("doc_groups_sharing") \
        .select("doc_groups(name, course_name, enabled, private, doc_count)") \
        .eq("destination_project_name", course_name) \
        .execute()

  def getAllConversationsForUserAndProject(self, user_email: str, project_name: str, curr_count: int = 0):
    return self.supabase_client.table('conversations').select(
        '*, messages(content_text, content_image_url, role, image_description, created_at).order(created_at, desc=True)',
        count='exact').eq('user_email',
                          user_email).eq('project_name',
                                         project_name).order('updated_at',
                                                             desc=True).limit(500).offset(curr_count).execute()

  def insertProject(self, project_info):
    return self.supabase_client.table("projects").insert(project_info).execute()
  
  def getPreAssignedAPIKeys(self, email: str):
    return self.supabase_client.table("pre_authorized_api_keys").select("*").contains("emails", '["' + email + '"]').execute()
  
  def getConversationsCreatedAtByCourse(self, course_name: str):
    try:
        count_response = self.supabase_client.table("llm-convo-monitor")\
            .select("created_at", count="exact")\
            .eq("course_name", course_name)\
            .execute()
        
        total_count = count_response.count if hasattr(count_response, 'count') else 0
        
        if total_count <= 0:
            print(f"No conversations found for course: {course_name}")
            return [], 0

        all_data = []
        batch_size = 1000
        start = 0

        while start < total_count:
            end = min(start + batch_size - 1, total_count - 1)

            try:
                response = self.supabase_client.table("llm-convo-monitor")\
                    .select("created_at")\
                    .eq("course_name", course_name)\
                    .range(start, end)\
                    .execute()

                if not response or not hasattr(response, 'data') or not response.data:
                    print(f"No data returned for range {start} to {end}.")
                    break

                all_data.extend(response.data)
                start += batch_size

            except Exception as batch_error:
                print(f"Error fetching batch {start}-{end}: {str(batch_error)}")
                continue

        if not all_data:
            print(f"No conversation data could be retrieved for course: {course_name}")
            return [], 0

        return all_data, len(all_data)

    except Exception as e:
        print(f"Error in getConversationsCreatedAtByCourse for {course_name}: {str(e)}")
        return [], 0
  
  def getProjectStats(self, project_name: str):
    try:
        response = self.supabase_client.table("project_stats").select("total_messages, total_conversations, unique_users")\
                    .eq("project_name", project_name).execute()
        
        if response and hasattr(response, 'data') and response.data:
            return response.data[0]
    except Exception as e:
        print(f"Error fetching project stats for {project_name}: {str(e)}")
    
    # Return default values if anything fails
    return {"total_messages": 0, "total_conversations": 0, "unique_users": 0}

      
  
  def getAllProjects(self):
    return self.supabase_client.table("projects").select("course_name, doc_map_id, convo_map_id, last_uploaded_doc_id, last_uploaded_convo_id").execute()