import os
import getpass
import platform

from langchain import hub
from langchain.chat_models import AzureChatOpenAI, ChatOpenAI
from langchain_experimental.plan_and_execute import (PlanAndExecute,
                                                     load_agent_executor,
                                                     load_chat_planner)

from ai_ta_backend.agents.tools import get_tools
from ai_ta_backend.agents.utils import fancier_trim_intermediate_steps


def get_user_info_string():
    username = getpass.getuser()
    current_working_directory = os.getcwd()
    operating_system = platform.system()
    default_shell = os.environ.get("SHELL")

    return f"[User Info]\nName: {username}\nCWD: {current_working_directory}\nSHELL: {default_shell}\nOS: {operating_system}"


class WorkflowAgent:
    def __init__(self, run_id_in_metadata):
        if os.environ['OPENAI_API_TYPE'] == 'azure':
            self.llm = AzureChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=3, request_timeout=60 * 3, deployment_name=os.environ['AZURE_OPENAI_ENGINE'])  # type: ignore
        else:
            self.llm: ChatOpenAI = ChatOpenAI(temperature=0, model="gpt-4-0613",max_retries=500, request_timeout=60 * 3)  # type: ignore
        self.agent = self.make_agent()
        self.run_id_in_metadata = run_id_in_metadata

    def run(self, input):
        result = self.agent.with_config({"run_name": "ML4BIO Plan & Execute Agent"}).invoke({"input":f"{input}"}, {"metadata": {"run_id_in_metadata": str(self.run_id_in_metadata)}})
        
        print(f"Result: {result}")
        return result

    def make_agent(self): 

        # TOOLS
        tools = get_tools(self.llm, sync=True)

        # PLANNER
        planner = load_chat_planner(self.llm, system_prompt=hub.pull("kastanday/ml4bio-rnaseq-planner").format(user_info=get_user_info_string))

        # EXECUTOR
        executor = load_agent_executor(self.llm, tools, verbose=True, trim_intermediate_steps=fancier_trim_intermediate_steps, handle_parsing_errors=True)

        # Create PlanAndExecute Agent
        workflow_agent = PlanAndExecute(planner=planner, executor=executor, verbose=True)

        return workflow_agent
        