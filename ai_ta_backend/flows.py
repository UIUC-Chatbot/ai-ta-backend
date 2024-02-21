import requests


class Flows():

  def __init__(self):
    self.flows = []
    self.url = "https://primary-production-1817.up.railway.app"

  def get_users(self, limit: int = 50, pagination: bool = True, api_key: str = ""):
    if not api_key:
      raise ValueError('api_key is required')
    all_users = []
    headers = {"X-N8N-API-KEY": api_key, "Accept": "application/json"}
    url = self.url+'/api/v1/users?limit=%s&includeRole=true' % str(limit)
    response = requests.get(url, headers=headers, timeout=8)
    data = response.json()
    if not pagination:
      return data['data']
    else:
      all_users.append(data['data'])
      cursor = data.get('nextCursor')
      while cursor is not None:
        url = self.url+'/api/v1/users?limit=%s&cursor=%s&includeRole=true' % (
            str(limit), cursor)
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
    url = self.url+f"/api/v1/executions?includeData=true&status=success&limit={limit}"
    response = requests.get(url, headers=headers, timeout=8)
    executions = response.json()
    if not pagination:
      all_executions = executions['data']
    else:
      all_executions = []
      all_executions.append(executions['data'])
      cursor = executions.get('nextCursor')
      while cursor is not None:
        url = f'self.url+/api/v1/executions?includeData=true&status=success&limit={str(limit)}&cursor={cursor}'
        response = requests.get(url, headers=headers, timeout=8)
        executions = response.json()
        all_executions.append(executions['data'])
        cursor = executions.get('nextCursor')
        if id:
          for execution in all_executions:
            if execution[0]['workflowId'] == id:
              return execution

    if id:
      for execution in executions['data']:
        if execution['workflowId'] == id:
          return execution
    else:
      return all_executions

  def get_workflows(self, limit, pagination: bool = True, api_key: str = ""):
    if not api_key:
      raise ValueError('api_key is required')
    headers = {"X-N8N-API-KEY": api_key, "Accept": "application/json"}
    url = self.url+f"/api/v1/workflows?limit={limit}"
    response = requests.get(url, headers=headers, timeout=8)

    workflows = response.json()

    if not pagination:
      return workflows['data']
    else:
      all_workflows = []
      all_workflows.append(workflows['data'])
      cursor = workflows.get('nextCursor')
      while cursor is not None:
        url = self.url+f"/api/v1/workflows?limit={limit}&cursor={cursor}"
        response = requests.get(url, headers=headers, timeout=8)
        workflows = response.json()
        all_workflows.append(workflows['data'])
        cursor = workflows.get('nextCursor')
    return all_workflows

  # TODO: Take the last one/ ALWAYS end in JSON
  def get_data(self, id):
    self.get_executions(20, id)

  def main_flow(self, hook: str, api_key: str = ""):
    if not api_key:
      raise ValueError('api_key is required')
    workflows = self.get_workflows(limit=20)
    id = workflows[0]['id'] + 1
    self.flows.append(id)
    self.execute_flow(hook)
    executions = self.get_executions(20, id, True, api_key)
    while id not in executions:
      executions = self.get_executions(20, id, True, api_key)

    return self.get_data(id)
