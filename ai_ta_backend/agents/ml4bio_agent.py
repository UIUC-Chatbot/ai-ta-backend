import getpass
import os
import platform

from langchain import hub
from langchain_community.chat_models import AzureChatOpenAI
from langchain_community.chat_models import ChatOpenAI
from langchain_experimental.plan_and_execute import load_agent_executor
from langchain_experimental.plan_and_execute import load_chat_planner
from langchain_experimental.plan_and_execute import PlanAndExecute

from ai_ta_backend.agents.tools import get_tools
from ai_ta_backend.agents.utils import fancier_trim_intermediate_steps


def get_user_info_string():
  username = getpass.getuser()
  current_working_directory = os.getcwd()
  operating_system = platform.system()
  default_shell = os.environ.get("SHELL")

  return f"[User Info]\nName: {username}\nCWD: {current_working_directory}\nSHELL: {default_shell}\nOS: {operating_system}"


class WorkflowAgent:

  def __init__(self, langsmith_run_id):
    print("PlannerAndExecute agent initialized")
    self.langsmith_run_id = langsmith_run_id
    if os.environ['OPENAI_API_TYPE'] == 'azure':
      self.llm = AzureChatOpenAI(temperature=0,
                                 model="gpt-4-0613",
                                 max_retries=3,
                                 request_timeout=60 * 3,
                                 deployment_name=os.environ['AZURE_OPENAI_ENGINE'])  # type: ignore
    else:
      self.llm: ChatOpenAI = ChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=500, request_timeout=60 * 3)  # type: ignore
    self.agent = self.make_agent()

  def run(self, input):
    result = self.agent.with_config({
        "run_name": "ML4BIO Plan & Execute Agent"
    }).invoke({"input": f"{input}"}, {"metadata": {
        "langsmith_run_id": str(self.langsmith_run_id)
    }})

    print(f"Result: {result}")
    return result

  def make_agent(self):
    # TOOLS
    tools = get_tools(langsmith_run_id=self.langsmith_run_id)

    # PLANNER
    planner = load_chat_planner(self.llm, system_prompt=hub.pull("kastanday/ml4bio-rnaseq-planner").format(user_info=get_user_info_string))

    # EXECUTOR
    executor = load_agent_executor(self.llm,
                                   tools,
                                   verbose=True,
                                   trim_intermediate_steps=fancier_trim_intermediate_steps,
                                   handle_parsing_errors=True)
    # executor = load_agent_executor(self.llm, tools, verbose=True, handle_parsing_errors=True)

    # Create PlanAndExecute Agent
    workflow_agent = PlanAndExecute(planner=planner, executor=executor, verbose=True)

    return workflow_agent
