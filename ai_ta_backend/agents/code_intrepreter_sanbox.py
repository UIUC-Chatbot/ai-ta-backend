import io
import threading
import time
import uuid
from typing import Any, Optional, Tuple

import termcolor
from e2b import CodeInterpreter, EnvVars, Sandbox


class E2B_class():

  def __init__(self, langsmith_run_id: str, env_vars: Optional[EnvVars] = None):
    '''
    # TODOs:
    1. Maybe `git clone` the repo to a temp folder and run the code there
    2. On agent finish, delete sandbox
    '''

    self.langsmith_run_id = langsmith_run_id
    self.sandbox = Sandbox(env_vars=env_vars)
    self.sandboxID = self.sandbox.id
    self.sandbox.keep_alive(60 * 60 * 1)  # 1 hour max
    self.command_timeout = 3 * 60  # 3 minutes
    self.existing_files = []
    self.working_dir = '/home/user/'
    self.curr_terminal_output = ''
    # self.install_base_packages()

  def install_base_packages(self):
    self.run_shell("pip install -U numpy pandas matplotlib seaborn scikit-learn scipy")

  def delete_sandbox(self):
    self.sandbox.close()

  def run_python_code(self, code: str):
    print(termcolor.colored(f"IN SHELL RUN PYTHON CODE...\n{code}", 'blue', attrs=['bold']))

    code_file = io.StringIO(code)
    code_file.name = f"{uuid.uuid4}_code.py"
    filepath = self.sandbox.upload_file(code_file)

    shell_output = self.run_shell(f"python {filepath}")
    return shell_output

  def run_shell(self, shell_command: str):
    print(termcolor.colored(f"IN SHELL EXECUTION with command: {shell_command}", 'blue', attrs=['bold']))
    self.curr_terminal_output = ''

    def on_exit():
      """Block until the command has exited"""
      self.exit_event.set()  # Signal that the command has exited

    start_time = time.monotonic()
    self.exit_event = threading.Event()
    self.sandbox.terminal.start(cmd=shell_command,
                                cwd=self.working_dir,
                                on_data=self.handle_terminal_on_data,
                                cols=120,
                                rows=80,
                                on_exit=on_exit,
                                timeout=self.command_timeout)

    self.exit_event.wait()  # Block until on_exit is called
    print(
        termcolor.colored(f"＄ Shell execution complete, Runtime: {(time.monotonic() - start_time):.2f} seconds",
                          'blue',
                          attrs=['bold']))
    return self.curr_terminal_output

  def handle_terminal_on_data(self, data: str):
    self.curr_terminal_output += str(data)
    print(termcolor.colored(data, 'yellow', attrs=['bold']))


def EXPERIMENTAL_run_simple_notebook(code,
                                     cwd: str = "",
                                     timeout: Optional[int] = None,
                                     env_vars: Optional[EnvVars] = None) -> Tuple[str, str, list[Any]]:
  """

  TBD if this is helpful; the one thing it uniquely does is grab matplotlib outputs. Simply, plt.show() becomes an "artifact" that can be downloaded.

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