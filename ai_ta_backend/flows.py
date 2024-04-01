import requests
import time
import os
import supabase
from urllib.parse import quote
import json


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

  def execute_flow(self, hook: str, data=None) -> None:
    if not data:
      data = {'field-0': ''}
    url = hook
    response = requests.post(url, files=data, timeout=60)
    body = response.json()
    if not response.ok:
      raise Exception(f"Error: {response.status_code} \n Message: {body.get('message')}")
    pass

  def get_executions(self, limit, id=None, pagination: bool = True, api_key: str = ""):
    if not api_key:
      raise ValueError('api_key is required')
    headers = {"X-N8N-API-KEY": api_key, "Accept": "application/json"}
    url = self.url + f"/api/v1/executions?includeData=true&limit={limit}"
    response = requests.get(url, headers=headers, timeout=8)
    executions = response.json()
    if not pagination:
      all_executions = executions['data']
    else:
      all_executions = []
      all_executions.append(executions['data'])
      cursor = executions.get('nextCursor')
      while cursor is not None:
        url = self.url + f'/api/v1/executions?includeData=true&limit={str(limit)}&cursor={quote(cursor)}'
        response = requests.get(url, headers=headers, timeout=8)
        executions = response.json()
        all_executions.append(executions['data'])
        cursor = executions.get('nextCursor')
        if id:
          for execution in all_executions:
            print(execution[0]['id'], ":ID:")
            if execution[0]['id'] == id:
              return execution

    if id:
      for execution in executions['data']:
        if execution['id'] == id:
          return execution
    else:
      return all_executions

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

  def get_hook(self, name: str, api_key: str = ""):
    work_flow = self.get_workflows(limit=100, api_key=api_key, workflow_name=name)
    if isinstance(work_flow, dict) and 'nodes' in work_flow:
      for node in work_flow['nodes']:
        if node['name'] == 'n8n Form Trigger':
          return node['parameters']['path']
    else:
      raise Exception('No nodes found in the workflow')

  def format_data(self, inputted, api_key: str, workflow_name):
    work_flow = self.get_workflows(100, api_key=api_key, workflow_name=workflow_name)
    print("Got workflow")
    values = []
    if isinstance(work_flow, dict) and 'nodes' in work_flow:
      print("passed if")
      for node in work_flow['nodes']:
        if node['name'] == 'n8n Form Trigger':
          values = node['parameters']['formFields']['values']
          print("found value")
    data = {}
    print(inputted)
    inputted = json.loads(inputted)
    print("Done with json")
    inputted = dict(inputted)
    print("Got data")
    for i, value in enumerate(values):
      field_name = 'field-' + str(i)
      data[value['fieldLabel']] = field_name
    new_data = {}
    for k, v in inputted.items():
      new_data[data[k]] = v
    print("Done with formatting")
    return new_data

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

  # TODO: NEED to have keyword args for workflows like Pest Detection.
  # TODO: make the supabase rpc call to make the transaction
  # What if some data takes longer to parse, so the transactional supabase call is wrong.
  def main_flow(self, name: str, api_key: str = "", data: str = ""):
    if not api_key:
      raise ValueError('api_key is required')
    print("Starting")
    hookId = self.get_hook(name, api_key)
    hook = self.url + f"/form/{hookId}"
    print("Hook!!!: ", hook)

    new_data = self.format_data(data, api_key, name)

    response = self.supabase_client.table('n8n_workflows').select("latest_workflow_id").execute()
    print("Got response")

    ids = []
    for row in dict(response)['data']:
      ids.append(row['latest_workflow_id'])

    if len(ids) > 0:
      id = max(ids) + 1
      print("Execution found in supabase: ", id)
    else:
      execution = self.get_executions(limit=1, api_key=api_key)
      print("Got executions")
      if execution:
        id = int(execution[0][0]['id']) + 1
        print("Execution found through n8n: ", id)
      else:
        raise Exception('No executions found')
    id = str(id)

    try:
      start_time = time.monotonic()
      self.supabase_client.table('n8n_workflows').insert({"latest_workflow_id": id, "is_locked": True}).execute()
      self.execute_flow(hook, new_data)
      print("Executed")
      print(f"⏰ Runtime to execute_flow(): {(time.monotonic() - start_time):.4f} seconds")
    except:
      self.supabase_client.table('n8n_workflows').delete().eq('latest_workflow_id', id).execute()
    finally:
      # TODO: Remove lock from Supabase table.
      self.supabase_client.table('n8n_workflows').update({"is_locked": False}).eq('latest_workflow_id', id).execute()

    try:
      executions = self.get_executions(20, id, True, api_key)
      print("Got executions", executions)
      while executions is None:
        executions = self.get_executions(1, id, True, api_key)
        print("Executions: ", executions)
        print("Can't find id in executions")
        time.sleep(1)
      print("Found id in executions ")
      self.supabase_client.table('n8n_workflows').delete().eq('latest_workflow_id', id).execute()
      print("Deleted id")
      print("Returning")
    except Exception as e:
      self.supabase_client.table('n8n_workflows').delete().eq('latest_workflow_id', id).execute()
      return {"error": str(e)}
    return executions
