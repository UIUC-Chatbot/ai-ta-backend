import requests
import time
import os
import supabase
from urllib.parse import quote


class Flows():

  def __init__(self):
    self.flows = []
    self.url = "https://primary-production-1817.up.railway.app"
    self.supabase_client = supabase.create_client(  # type: ignore
        supabase_url=os.environ['SUPABASE_URL'], supabase_key=os.environ['SUPABASE_API_KEY'])

  def get_users(self, limit: int = 50, pagination: bool = True, api_key: str = ""):
    if not api_key:
      raise ValueError('api_key is required')
    all_users = []
    headers = {"X-N8N-API-KEY": api_key, "Accept": "application/json"}
    url = self.url + '/api/v1/users?limit=%s&includeRole=true' % str(limit)
    response = requests.get(url, headers=headers, timeout=8)
    data = response.json()
    if not pagination:
      return data['data']
    else:
      all_users.append(data['data'])
      cursor = data.get('nextCursor')
      while cursor is not None:
        url = self.url + '/api/v1/users?limit=%s&cursor=%s&includeRole=true' % (str(limit), quote(cursor))
        response = requests.get(url, headers=headers, timeout=8)
        data = response.json()
        all_users.append(data['data'])
        cursor = data.get('nextCursor')

    return all_users

  def execute_flow(self, hook: str, api_key: str = ""):
    if not api_key:
      raise ValueError('api_key is required')
    headers = {"X-N8N-API-KEY": api_key, "Accept": "application/json"}
    url = hook
    response = requests.get(url, headers=headers, timeout=8)
    body = response.content
    return body.decode('utf-8')

  def get_executions(self, limit, id=None, pagination: bool = True, api_key: str = ""):
    if not api_key:
      raise ValueError('api_key is required')
    headers = {"X-N8N-API-KEY": api_key, "Accept": "application/json"}
    url = self.url + f"/api/v1/executions?includeData=true&status=success&limit={limit}"
    response = requests.get(url, headers=headers, timeout=8)
    executions = response.json()
    if not pagination:
      all_executions = executions['data']
    else:
      all_executions = []
      all_executions.append(executions['data'])
      cursor = executions.get('nextCursor')
      while cursor is not None:
        url = self.url + f'/api/v1/executions?includeData=true&status=success&limit={str(limit)}&cursor={quote(cursor)}'
        response = requests.get(url, headers=headers, timeout=8)
        executions = response.json()
        all_executions.append(executions['data'])
        cursor = executions.get('nextCursor')
        if id:
          for execution in all_executions:
            if execution[0]['id'] == id:
              return execution

    if id:
      for execution in executions['data']:
        if execution['id'] == id:
          return execution
    else:
      return all_executions

  def get_hook(self, name: str, api_key: str = ""):
    work_flow = self.get_workflows(limit=100, api_key=api_key, workflow_name=name)
    for node in work_flow.get('nodes'):  # type: ignore
      if node['name'] == 'Webhook':
        return node['webhookId']
    pass

  def get_workflows(self,
                    limit,
                    pagination: bool = True,
                    api_key: str = "",
                    active: bool = False,
                    workflow_name: str = ''):
    if not api_key:
      raise ValueError('api_key is required')
    headers = {"X-N8N-API-KEY": api_key, "Accept": "application/json"}
    url = self.url + f"/api/v1/workflows?limit={limit}"
    if active:
      url = url + "&active=true"
    response = requests.get(url, headers=headers, timeout=8)
    workflows = response.json()
    if workflows.get('message') == 'unauthorized' and not response.ok:
      raise Exception('Unauthorized')

    if not pagination:
      return workflows['data']
    else:
      all_workflows = []
      all_workflows.append(workflows['data'])
      cursor = workflows.get('nextCursor')
      while cursor is not None:
        url = self.url + f"/api/v1/workflows?limit={limit}&cursor={quote(cursor)}"
        response = requests.get(url, headers=headers, timeout=8)
        workflows = response.json()
        all_workflows.append(workflows['data'])
        cursor = workflows.get('nextCursor')

    if workflow_name:
      for workflow in all_workflows[0]:
        if workflow['name'] == workflow_name:
          return workflow
      else:
        raise Exception('Workflow not found')
    return all_workflows

  # TODO: activate and disactivate workflows

  def switch_workflow(self, id, api_key: str = "", activate: 'str' = 'True'):
    if not api_key:
      raise ValueError('api_key is required')
    headers = {"X-N8N-API-KEY": api_key, "Accept": "application/json"}
    if activate == "True" or activate == "true":
      url = self.url + f"/api/v1/workflows/{id}/activate"
    else:
      url = self.url + f"/api/v1/workflows/{id}/deactivate"
    response = requests.post(url, headers=headers, timeout=8)
    result = response.json()
    # if result.get('message'):
    #   raise Exception(result.get('message'))
    return result

  # Making this so it can be synchronous so that OpenAi API can call it.
  # TODO: Status update on ID, running/done/error
  # Todo: Before running, check if it is active by fetching the latest execution, increment if necessary and then run the flow.
  # TODO: Create a dummy endpoint to pass to openai function call expecting n8n webhook and necessary parameters in the request.

  # TODO: Take the last one/ ALWAYS end in JSON
  def get_data(self, id):
    self.get_executions(20, id)

  # TODO: Make the list of flows through supabase
  def main_flow(self, name: str, api_key: str = ""):
    if not api_key:
      raise ValueError('api_key is required')
    execution = self.get_executions(limit=1, api_key=api_key)
    hookId = self.get_hook(name, api_key)
    hook = self.url + f"/webhook/{hookId}"
    print("Hook!!!: ", hook)

    response = self.supabase_client.table('n8n_api_keys').select("*").execute()

    ids = []
    for row in dict(response)['data']:
      ids.append(row['id'])

    if len(ids) > 0:
      id = max(ids) + 1
      print("Execution found in supabase: ", id)
    else:
      if execution:
        id = int(execution[0][0]['id']) + 1
        print("Execution found through n8n: ", id)
      else:
        raise Exception('No executions found')
    id = str(id)

    self.supabase_client.table('n8n_api_keys').insert({"id": id}).execute()
    try:
      self.execute_flow(hook, api_key)
      print("Executed")
      executions = self.get_executions(20, id, True, api_key)
      print("Got executions", executions)
      while executions is None:
        executions = self.get_executions(1, id, True, api_key)
        print("Executions: ", executions)
        print("Can't find id in executions")
        time.sleep(1)
    except Exception as e:
      self.supabase_client.table('n8n_api_keys').delete().eq('id', id).execute()
      return {"error": str(e)}
    print("Found id in executions ")
    self.supabase_client.table('n8n_api_keys').delete().eq('id', id).execute()
    print("Deleted id")
    print("Returning")
    return executions
