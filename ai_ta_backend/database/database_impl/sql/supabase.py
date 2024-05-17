import os

import supabase
from injector import inject

from ai_ta_backend.database.base_sql import BaseSQLDatabase


class SQLDatabase(BaseSQLDatabase):

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
    return self.supabase_client.table("llm-convo-monitor").select("*").eq("course_name", course_name).order('id', desc=False).execute()
  
  def getCountFromLLMConvoMonitor(self, course_name: str, last_id: int):
    if last_id == 0:
      return self.supabase_client.table("llm-convo-monitor").select("id", count='exact').eq("course_name", course_name).order('id', desc=False).execute()
    else:
      return self.supabase_client.table("llm-convo-monitor").select("id", count='exact').eq("course_name", course_name).gt("id", last_id).order('id', desc=False).execute()
  
  def getDocMapFromProjects(self, course_name: str):
    return self.supabase_client.table("projects").select("doc_map_id").eq("course_name", course_name).execute()
  
  def getConvoMapFromProjects(self, course_name: str):
    return self.supabase_client.table("projects").select("*").eq("course_name", course_name).execute()
  
  def updateProjects(self, course_name: str, data: dict):
    return self.supabase_client.table("projects").update(data).eq("course_name", course_name).execute()
  
  def getLatestWorkflowId(self):
    return self.supabase_client.table('n8n_workflows').select("latest_workflow_id").execute()
  
  def lockWorkflow(self, id: str):
    return self.supabase_client.table('n8n_workflows').insert({"latest_workflow_id": id, "is_locked": True}).execute()
  
  def deleteLatestWorkflowId(self, id: str):
    return self.supabase_client.table('n8n_workflows').delete().eq('latest_workflow_id', id).execute()
  
  def unlockWorkflow(self, id: str):
    return self.supabase_client.table('n8n_workflows').update({"is_locked": False}).eq('latest_workflow_id', id).execute()

  def getConversation(self, course_name: str, key: str, value: str):
    return self.supabase_client.table("llm-convo-monitor").select("*").eq(key, value).eq("course_name", course_name).execute()

  
