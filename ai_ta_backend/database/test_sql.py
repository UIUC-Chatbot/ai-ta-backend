import os
import pytest
from unittest.mock import MagicMock, patch
from .sql import SQLDatabase

@pytest.fixture
def mock_supabase_client():
  return MagicMock()

@pytest.fixture
def sql_database(mock_supabase_client):
  with patch('supabase.create_client', return_value=mock_supabase_client):
    return SQLDatabase()

def test_getAllMaterialsForCourse(sql_database, mock_supabase_client):
  course_name = "test_course"
  sql_database.getAllMaterialsForCourse(course_name)
  mock_supabase_client.table.assert_called_with(os.environ['SUPABASE_DOCUMENTS_TABLE'])
  mock_supabase_client.table().select.assert_called_with('course_name, s3_path, readable_filename, url, base_url')
  mock_supabase_client.table().select().eq.assert_called_with('course_name', course_name)
  mock_supabase_client.table().select().eq().execute.assert_called()

def test_getMaterialsForCourseAndS3Path(sql_database, mock_supabase_client):
  course_name = "test_course"
  s3_path = "test_path"
  sql_database.getMaterialsForCourseAndS3Path(course_name, s3_path)
  mock_supabase_client.from_.assert_called_with(os.environ['SUPABASE_DOCUMENTS_TABLE'])
  mock_supabase_client.from_().select.assert_called_with("id, s3_path, contexts")
  mock_supabase_client.from_().select().eq.assert_any_call('s3_path', s3_path)
  mock_supabase_client.from_().select().eq().eq.assert_called_with('course_name', course_name)
  mock_supabase_client.from_().select().eq().eq().execute.assert_called()

def test_getMaterialsForCourseAndKeyAndValue(sql_database, mock_supabase_client):
  course_name = "test_course"
  key = "test_key"
  value = "test_value"
  sql_database.getMaterialsForCourseAndKeyAndValue(course_name, key, value)
  mock_supabase_client.from_.assert_called_with(os.environ['SUPABASE_DOCUMENTS_TABLE'])
  mock_supabase_client.from_().select.assert_called_with("id, s3_path, contexts")
  mock_supabase_client.from_().select().eq.assert_any_call(key, value)
  mock_supabase_client.from_().select().eq().eq.assert_called_with('course_name', course_name)
  mock_supabase_client.from_().select().eq().eq().execute.assert_called()

def test_deleteMaterialsForCourseAndKeyAndValue(sql_database, mock_supabase_client):
  course_name = "test_course"
  key = "test_key"
  value = "test_value"
  sql_database.deleteMaterialsForCourseAndKeyAndValue(course_name, key, value)
  mock_supabase_client.from_.assert_called_with(os.environ['SUPABASE_DOCUMENTS_TABLE'])
  mock_supabase_client.from_().delete.assert_called()
  mock_supabase_client.from_().delete().eq.assert_any_call(key, value)
  mock_supabase_client.from_().delete().eq().eq.assert_called_with('course_name', course_name)
  mock_supabase_client.from_().delete().eq().eq().execute.assert_called()

def test_deleteMaterialsForCourseAndS3Path(sql_database, mock_supabase_client):
  course_name = "test_course"
  s3_path = "test_path"
  sql_database.deleteMaterialsForCourseAndS3Path(course_name, s3_path)
  mock_supabase_client.from_.assert_called_with(os.environ['SUPABASE_DOCUMENTS_TABLE'])
  mock_supabase_client.from_().delete.assert_called()
  mock_supabase_client.from_().delete().eq.assert_any_call('s3_path', s3_path)
  mock_supabase_client.from_().delete().eq().eq.assert_called_with('course_name', course_name)
  mock_supabase_client.from_().delete().eq().eq().execute.assert_called()

def test_getProjectsMapForCourse(sql_database, mock_supabase_client):
  course_name = "test_course"
  sql_database.getProjectsMapForCourse(course_name)
  mock_supabase_client.table.assert_called_with("projects")
  mock_supabase_client.table().select.assert_called_with("doc_map_id")
  mock_supabase_client.table().select().eq.assert_called_with("course_name", course_name)
  mock_supabase_client.table().select().eq().execute.assert_called()

def test_getDocumentsBetweenDates(sql_database, mock_supabase_client):
  course_name = "test_course"
  from_date = "2023-01-01"
  to_date = "2023-12-31"
  table_name = "test_table"
  sql_database.getDocumentsBetweenDates(course_name, from_date, to_date, table_name)
  mock_supabase_client.table.assert_called_with(table_name)
  mock_supabase_client.table().select.assert_called_with("id", count='exact')
  mock_supabase_client.table().select().eq.assert_called_with("course_name", course_name)
  mock_supabase_client.table().select().eq().gte.assert_called_with('created_at', from_date)
  mock_supabase_client.table().select().eq().gte().lte.assert_called_with('created_at', to_date)
  mock_supabase_client.table().select().eq().gte().lte().order.assert_called_with('id', desc=False)
  mock_supabase_client.table().select().eq().gte().lte().order().execute.assert_called()

def test_getAllFromTableForDownloadType(sql_database, mock_supabase_client):
  course_name = "test_course"
  download_type = "documents"
  first_id = 1
  sql_database.getAllFromTableForDownloadType(course_name, download_type, first_id)
  mock_supabase_client.table.assert_called_with("documents")
  mock_supabase_client.table().select.assert_called_with("*")
  mock_supabase_client.table().select().eq.assert_called_with("course_name", course_name)
  mock_supabase_client.table().select().eq().gte.assert_called_with('id', first_id)
  mock_supabase_client.table().select().eq().gte().order.assert_called_with('id', desc=False)
  mock_supabase_client.table().select().eq().gte().order().limit.assert_called_with(100)
  mock_supabase_client.table().select().eq().gte().order().limit().execute.assert_called()

def test_getAllConversationsBetweenIds(sql_database, mock_supabase_client):
  course_name = "test_course"
  first_id = 1
  last_id = 10
  limit = 50
  sql_database.getAllConversationsBetweenIds(course_name, first_id, last_id, limit)
  mock_supabase_client.table.assert_called_with("llm-convo-monitor")
  mock_supabase_client.table().select.assert_called_with("*")
  mock_supabase_client.table().select().eq.assert_called_with("course_name", course_name)
  mock_supabase_client.table().select().eq().gte.assert_called_with('id', first_id)
  mock_supabase_client.table().select().eq().gte().lte.assert_called_with('id', last_id)
  mock_supabase_client.table().select().eq().gte().lte().order.assert_called_with('id', desc=False)
  mock_supabase_client.table().select().eq().gte().lte().order().limit.assert_called_with(limit)
  mock_supabase_client.table().select().eq().gte().lte().order().limit().execute.assert_called()

def test_getDocsForIdsGte(sql_database, mock_supabase_client):
  course_name = "test_course"
  first_id = 1
  fields = "*"
  limit = 100
  sql_database.getDocsForIdsGte(course_name, first_id, fields, limit)
  mock_supabase_client.table.assert_called_with("documents")
  mock_supabase_client.table().select.assert_called_with(fields)
  mock_supabase_client.table().select().eq.assert_called_with("course_name", course_name)
  mock_supabase_client.table().select().eq().gte.assert_called_with('id', first_id)
  mock_supabase_client.table().select().eq().gte().order.assert_called_with('id', desc=False)
  mock_supabase_client.table().select().eq().gte().order().limit.assert_called_with(limit)
  mock_supabase_client.table().select().eq().gte().order().limit().execute.assert_called()

def test_insertProjectInfo(sql_database, mock_supabase_client):
  project_info = {"name": "test_project"}
  sql_database.insertProjectInfo(project_info)
  mock_supabase_client.table.assert_called_with("projects")
  mock_supabase_client.table().insert.assert_called_with(project_info)
  mock_supabase_client.table().insert().execute.assert_called()

def test_getAllFromLLMConvoMonitor(sql_database, mock_supabase_client):
  course_name = "test_course"
  sql_database.getAllFromLLMConvoMonitor(course_name)
  mock_supabase_client.table.assert_called_with("llm-convo-monitor")
  mock_supabase_client.table().select.assert_called_with("*")
  mock_supabase_client.table().select().eq.assert_called_with("course_name", course_name)
  mock_supabase_client.table().select().eq().order.assert_called_with('id', desc=False)
  mock_supabase_client.table().select().eq().order().execute.assert_called()

def test_getCountFromLLMConvoMonitor(sql_database, mock_supabase_client):
  course_name = "test_course"
  last_id = 0
  sql_database.getCountFromLLMConvoMonitor(course_name, last_id)
  mock_supabase_client.table.assert_called_with("llm-convo-monitor")
  mock_supabase_client.table().select.assert_called_with("id", count='exact')
  mock_supabase_client.table().select().eq.assert_called_with("course_name", course_name)
  mock_supabase_client.table().select().eq().order.assert_called_with('id', desc=False)
  mock_supabase_client.table().select().eq().order().execute.assert_called()

def test_getDocMapFromProjects(sql_database, mock_supabase_client):
  course_name = "test_course"
  sql_database.getDocMapFromProjects(course_name)
  mock_supabase_client.table.assert_called_with("projects")
  mock_supabase_client.table().select.assert_called_with("doc_map_id")
  mock_supabase_client.table().select().eq.assert_called_with("course_name", course_name)
  mock_supabase_client.table().select().eq().execute.assert_called()

def test_getConvoMapFromProjects(sql_database, mock_supabase_client):
  course_name = "test_course"
  sql_database.getConvoMapFromProjects(course_name)
  mock_supabase_client.table.assert_called_with("projects")
  mock_supabase_client.table().select.assert_called_with("*")
  mock_supabase_client.table().select().eq.assert_called_with("course_name", course_name)
  mock_supabase_client.table().select().eq().execute.assert_called()

def test_updateProjects(sql_database, mock_supabase_client):
  course_name = "test_course"
  data = {"name": "updated_project"}
  sql_database.updateProjects(course_name, data)
  mock_supabase_client.table.assert_called_with("projects")
  mock_supabase_client.table().update.assert_called_with(data)
  mock_supabase_client.table().update().eq.assert_called_with("course_name", course_name)
  mock_supabase_client.table().update().eq().execute.assert_called()

def test_getLatestWorkflowId(sql_database, mock_supabase_client):
  sql_database.getLatestWorkflowId()
  mock_supabase_client.table.assert_called_with('n8n_workflows')
  mock_supabase_client.table().select.assert_called_with("*")
  mock_supabase_client.table().select().execute.assert_called()

def test_lockWorkflow(sql_database, mock_supabase_client):
  workflow_id = 1
  sql_database.lockWorkflow(workflow_id)
  mock_supabase_client.table.assert_called_with('n8n_workflows')
  mock_supabase_client.table().insert.assert_called_with({"latest_workflow_id": workflow_id, "is_locked": True})
  mock_supabase_client.table().insert().execute.assert_called()

def test_deleteLatestWorkflowId(sql_database, mock_supabase_client):
  workflow_id = 1
  sql_database.deleteLatestWorkflowId(workflow_id)
  mock_supabase_client.table.assert_called_with('n8n_workflows')
  mock_supabase_client.table().delete.assert_called()
  mock_supabase_client.table().delete().eq.assert_called_with('latest_workflow_id', workflow_id)
  mock_supabase_client.table().delete().eq().execute.assert_called()

def test_unlockWorkflow(sql_database, mock_supabase_client):
  workflow_id = 1
  sql_database.unlockWorkflow(workflow_id)
  mock_supabase_client.table.assert_called_with('n8n_workflows')
  mock_supabase_client.table().update.assert_called_with({"is_locked": False})
  mock_supabase_client.table().update().eq.assert_called_with('latest_workflow_id', workflow_id)
  mock_supabase_client.table().update().eq().execute.assert_called()

def test_check_and_lock_flow(sql_database, mock_supabase_client):
  workflow_id = 1
  sql_database.check_and_lock_flow(workflow_id)
  mock_supabase_client.rpc.assert_called_with('check_and_lock_flows_v2', {'id': workflow_id})
  mock_supabase_client.rpc().execute.assert_called()

def test_getConversation(sql_database, mock_supabase_client):
  course_name = "test_course"
  key = "test_key"
  value = "test_value"
  sql_database.getConversation(course_name, key, value)
  mock_supabase_client.table.assert_called_with("llm-convo-monitor")
  mock_supabase_client.table().select.assert_called_with("*")
  mock_supabase_client.table().select().eq.assert_any_call(key, value)
  mock_supabase_client.table().select().eq().eq.assert_called_with("course_name", course_name)
  mock_supabase_client.table().select().eq().eq().execute.assert_called()

def test_getDisabledDocGroups(sql_database, mock_supabase_client):
  course_name = "test_course"
  sql_database.getDisabledDocGroups(course_name)
  mock_supabase_client.table.assert_called_with("doc_groups")
  mock_supabase_client.table().select.assert_called_with("name")
  mock_supabase_client.table().select().eq.assert_any_call("course_name", course_name)
  mock_supabase_client.table().select().eq().eq.assert_called_with("enabled", False)
  mock_supabase_client.table().select().eq().eq().execute.assert_called()

def test_getAllConversationsForUserAndProject(sql_database, mock_supabase_client):
  user_email = "test_user@example.com"
  project_name = "test_project"
  curr_count = 0
  sql_database.getAllConversationsForUserAndProject(user_email, project_name, curr_count)
  mock_supabase_client.table.assert_called_with('conversations')
  mock_supabase_client.table().select.assert_called_with(
    '*, messages(content_text, content_image_url, role, image_description, created_at).order(created_at, desc=True)',
    count='exact')
  mock_supabase_client.table().select().eq.assert_any_call('user_email', user_email)
  mock_supabase_client.table().select().eq().eq.assert_called_with('project_name', project_name)
  mock_supabase_client.table().select().eq().eq().order.assert_called_with('updated_at', desc=True)
  mock_supabase_client.table().select().eq().eq().order().limit.assert_called_with(500)
  mock_supabase_client.table().select().eq().eq().order().limit().offset.assert_called_with(curr_count)
  mock_supabase_client.table().select().eq().eq().order().limit().offset().execute.assert_called()

def test_insertProject(sql_database, mock_supabase_client):
  project_info = {"name": "test_project"}
  sql_database.insertProject(project_info)
  mock_supabase_client.table.assert_called_with("projects")
  mock_supabase_client.table().insert.assert_called_with(project_info)
  mock_supabase_client.table().insert().execute.assert_called()

def test_getPreAssignedAPIKeys(sql_database, mock_supabase_client):
  email = "test_user@example.com"
  sql_database.getPreAssignedAPIKeys(email)
  mock_supabase_client.table.assert_called_with("pre_authorized_api_keys")
  mock_supabase_client.table().select.assert_called_with("*")
  mock_supabase_client.table().select().contains.assert_called_with("emails", '["' + email + '"]')
  mock_supabase_client.table().select().contains().execute.assert_called()