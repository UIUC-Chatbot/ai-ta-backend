import pycurl
import json
from io import BytesIO


class Flows():

  def __init__(self):
    self.flows = []

  def get_users(self, limit: int = 50, pagination: bool = True, api_key: str = None):
    all_users = []
    headers = ["X-N8N-API-KEY: %s" % api_key, "Accept: application/json"]
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL,
             'https://primary-production-60d0.up.railway.app/api/v1/users?limit=%s&includeRole=true' % str(limit))
    c.setopt(c.HTTPHEADER, headers)
    c.setopt(c.WRITEDATA, buffer)
    c.perform()
    c.close()
    body = buffer.getvalue()
    data = json.loads(body.decode('utf-8'))
    if not pagination:
      return data['data']
    else:
      all_users.append(data['data'])
      cursor = data.get('nextCursor')
      while cursor is not None:
        buffer = BytesIO()
        cursor = data.get('nextCursor')
        c = pycurl.Curl()
        c.setopt(c.HTTPHEADER, headers)
        c.setopt(c.WRITEDATA, buffer)
        c.setopt(
            c.URL, 'https://primary-production-60d0.up.railway.app/api/v1/users?limit=%s&cursor=%s&includeRole=true' %
            (str(limit), cursor))
        c.perform()
        c.close()
        body = buffer.getvalue()
        data = json.loads(body.decode('utf-8'))
        all_users.append(data['data'])
        cursor = data.get('nextCursor')

    return all_users

  def execute_flow(self, hook: str, api_key: str = None):
    headers = ["X-N8N-API-KEY: %s" % api_key, "Accept: application/json"]
    url = hook
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.HTTPHEADER, headers)
    c.setopt(c.WRITEDATA, buffer)
    c.perform()
    c.close()

    body = buffer.getvalue()
    return body.decode('utf-8')

  def get_executions(self, limit, id=None, pagination: bool = True, api_key: str = None):
    headers = ["X-N8N-API-KEY: %s" % api_key, "Accept: application/json"]
    url = "https://primary-production-60d0.up.railway.app/api/v1/executions?includeData=true&status=success&limit=%s" % limit
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.HTTPHEADER, headers)
    c.setopt(c.WRITEDATA, buffer)
    c.perform()
    c.close()

    body = buffer.getvalue()
    executions = json.loads(body.decode('utf-8'))
    if not pagination:
      all_executions = executions['data']
    else:
      all_executions = []
      all_executions.append(executions['data'])
      cursor = executions.get('nextCursor')
      while cursor is not None:
        buffer = BytesIO()
        cursor = executions.get('nextCursor')
        c = pycurl.Curl()
        c.setopt(c.HTTPHEADER, headers)
        c.setopt(c.WRITEDATA, buffer)
        c.setopt(
            c.URL,
            'https://primary-production-60d0.up.railway.app/api/v1/executions?includeData=true&status=success&limit=%s&cursor=%s'
            % (str(limit), cursor))
        c.perform()
        c.close()
        body = buffer.getvalue()
        executions = json.loads(body.decode('utf-8'))
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

  def get_workflows(self, limit, pagination: bool = True, api_key: str = None):
    headers = ["X-N8N-API-KEY: %s" % api_key, "Accept: application/json"]
    url = "https://primary-production-60d0.up.railway.app/api/v1/workflows?limit=%s" % limit
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.HTTPHEADER, headers)
    c.setopt(c.WRITEDATA, buffer)
    c.perform()
    c.close()

    body = buffer.getvalue()
    workflows = json.loads(body.decode('utf-8'))

    if not pagination:
      return workflows['data']
    else:
      all_workflows = []
      all_workflows.append(workflows['data'])
      cursor = workflows.get('nextCursor')
      while cursor is not None:
        buffer = BytesIO()
        cursor = workflows.get('nextCursor')
        c = pycurl.Curl()
        c.setopt(c.HTTPHEADER, headers)
        c.setopt(c.WRITEDATA, buffer)
        c.setopt(
            c.URL,
            'https://primary-production-60d0.up.railway.app/api/v1/workflows?limit=%s&cursor=%s' % (str(limit), cursor))
        c.perform()
        c.close()
        body = buffer.getvalue()
        workflows = json.loads(body.decode('utf-8'))
        all_workflows.append(workflows['data'])
        cursor = workflows.get('nextCursor')
    return all_workflows

  # TODO: Take the last one/ ALWAYS end in JSON
  def get_data(self, id):
    self.get_executions(20, id)

  def main_flow(self, hook: str, api_key: str = None):
    workflows = self.get_workflows(20, api_key)
    id = workflows[0]['id'] + 1
    self.flows.append(id)
    self.execute_flow(hook)
    executions = self.get_executions(20, id, True, api_key)
    while id not in executions:
      executions = self.get_executions(20, id, True, api_key)

    return self.get_data(id)
