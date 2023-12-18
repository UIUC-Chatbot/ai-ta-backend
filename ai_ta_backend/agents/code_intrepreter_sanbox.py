from typing import Any, Optional, Tuple
from e2b import CodeInterpreter, EnvVars, Sandbox

# TODOs:
'''
1. Maybe git clone the repo to a temp folder and run the code there
'''

# create sandbox, set timeout to 24 hours.
# On init, create sandbox. Install reasonable packages.
# 3 functions: 
#   1. run python code
#   2. run shell code
#   3. file management (upload, download, delete)


class E2B_class():
  def __init__(self, langsmith_run_id: str):
    self.langsmith_run_id = langsmith_run_id
    # self.sandboxID = create_sandbox() # todo: keepalive
    # TODO on agent finish, delete sandbox
  
  def delete_sandbox(self):
    pass
  
  # def run_code(self, code):
  def run_python_code(self, code: str):
    # todo: reconnect to sandbox
    print("IN RUN PYTHON CODE")
    print("CODE: ", code)
    print("LANGSMITH RUN ID: ", self.langsmith_run_id)
    return "Success (placeholder)"
  
  # def run_shell(code, cwd: str = "", timeout: Optional[int] = None, env_vars: Optional[EnvVars] = None) -> Tuple[str, str, list[Any]]:
  #   sandbox.run_command("sudo apt update")
  def run_shell(self, shell_command: str):
    # todo: reconnect to sandbox
    print("IN SHELL EXECUTION")
    print("CODE: ", shell_command)
    print("LANGSMITH RUN ID: ", self.langsmith_run_id)
    return "Success (placeholder)"

# TODOs: 
def create_sandbox():
  sandbox = Sandbox(env_vars={"FOO": "Hello"})
  sandboxID = sandbox.id
  return sandboxID



def run_code(code, cwd: str = "", timeout: Optional[int] = None, env_vars: Optional[EnvVars] = None) -> Tuple[str, str, list[Any]]:
  """_summary_

  Args:
      code (_type_): _description_
      timeout (Optional[int], optional): _description_. Defaults to None.
      cwd (Optional[str], optional): _description_. Defaults to "".
      env_vars (Optional[EnvVars], optional): _description_. Defaults to None.

  Returns:
      Tuple[str, str, list[Any]]: _description_
  """

  # Don't use code intrepreter -- super limited, no shell access.
  # sandbox = Sandbox(env_vars={"FOO": "Hello"})
  sandbox = CodeInterpreter(env_vars={"FOO": "Hello"})

  # sandbox.install_python_packages('ffmpeg')
  # sandbox.install_system_packages('ffmpeg')
  # with open("path/to/local/file", "rb") as f:
  #   remote_path = sandbox.upload_file(f)  


  stdout, stderr, artifacts = sandbox.run_python(code, timeout=timeout, cwd=cwd, env_vars=env_vars)

  artifact_files = []
  for artifact in artifacts:
    # Now you can save this file, send it to frontend, or anything else
    artifact_files.append(artifact.download())

  sandbox.close()
  return stdout, stderr, artifact_files
