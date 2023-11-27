import getpass
import json
import os
import platform
from typing import List

from langchain import hub
from langchain.chat_models import AzureChatOpenAI, ChatOpenAI
from langchain.agents import AgentType, initialize_agent
from langchain.schema.language_model import BaseLanguageModel
from langchain_experimental.plan_and_execute import (PlanAndExecute,
                                                     load_agent_executor,
                                                     load_chat_planner)
from langchain.agents.agent import AgentExecutor
from langchain.agents.structured_chat.base import StructuredChatAgent
from langchain.schema.language_model import BaseLanguageModel
from langchain.tools import BaseTool

from langchain_experimental.plan_and_execute.executors.base import ChainExecutor
from .tools import get_tools
from .utils import fancier_trim_intermediate_steps
from .utils import SupabaseDB
import ai_ta_backend.agents.customcallbacks as customcallbacks

HUMAN_MESSAGE_TEMPLATE = """Previous steps: {previous_steps}

Current objective: {current_step}

{agent_scratchpad}"""

TASK_PREFIX = """{objective}

"""

MEMORY_CONTEXT = """
Memory:
Tools used in chronological order(1 is oldest) : {tools_used}
Actions taken in chronological order(1 is oldest) : {agent_action_steps}
"""



def get_user_info_string():
    username = getpass.getuser()
    current_working_directory = os.getcwd()
    operating_system = platform.system()
    default_shell = os.environ.get("SHELL")

    return f"[User Info]\nName: {username}\nCWD: {current_working_directory}\nSHELL: {default_shell}\nOS: {operating_system}"


def get_memory_context(table_name: str, image_name: str):
    db = SupabaseDB(table_name=table_name, image_name=image_name)
    tools_used, action_data_string = "", ""

    if db.is_exists_image():
        tool_data = db.fetch_field_from_db("on_tool_start")
        if tool_data:
            tools_used = [item['name'] for item in tool_data]
            tools_used = ", ".join(tools_used)

        action_data = db.fetch_field_from_db("on_agent_action")
        if action_data:
            action_data_string = [item['log'] for item in action_data]
            action_data_string = ", ".join(action_data_string)

    return MEMORY_CONTEXT.format(
        tools_used=tools_used,
        agent_action_steps=action_data_string,
    )


class WorkflowAgent:
    def __init__(self, run_id_in_metadata, image_name):
        self.run_id_in_metadata = run_id_in_metadata
        self.image_name = image_name
        self.callback_handler = customcallbacks.CustomCallbackHandler(run_id=self.run_id_in_metadata,
                                                                      image_name=self.image_name)
        if os.environ['OPENAI_API_TYPE'] == 'azure':
            self.llm = AzureChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=3, request_timeout=60 * 3,
                                       deployment_name=os.environ['AZURE_OPENAI_ENGINE'],
                                       callbacks=[self.callback_handler])  # type: ignore
        else:
            self.llm: ChatOpenAI = ChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=500,
                                              request_timeout=60 * 3,
                                              callbacks=[self.callback_handler])  # type: ignore

        self.agent = self.make_agent()

    def run(self, input):
        result = self.agent.with_config({"run_name": "ML4BIO Plan & Execute Agent"}).invoke({"input": f"{input}"}, {
            "metadata": {"run_id_in_metadata": str(self.run_id_in_metadata)}})

        print(f"Result: {result}")
        return result

    def custom_load_agent_executor(self,
                                llm: BaseLanguageModel,
                                tools: List[BaseTool],
                                verbose: bool = False,
                                callbacks: List = [],
                                include_task_in_prompt: bool = False,
                                **kwargs
        ) -> ChainExecutor:
        """
        Load an agent executor.

        Args:
            llm: BaseLanguageModel
            tools: List[BaseTool]
            verbose: bool. Defaults to False.
            include_task_in_prompt: bool. Defaults to False.

        Returns:
            ChainExecutor
        """
        memory_context = get_memory_context(table_name="docker_images", image_name=self.image_name)
        print("Memory Context: ", memory_context)

        input_variables = ["previous_steps", "current_step", "agent_scratchpad"]
        template = HUMAN_MESSAGE_TEMPLATE + memory_context

        if include_task_in_prompt:
            input_variables.append("objective")
            template = TASK_PREFIX + template

        agent = StructuredChatAgent.from_llm_and_tools(
            llm,
            tools,
            human_message_template=template,
            input_variables=input_variables,
        )
        agent_executor = AgentExecutor.from_agent_and_tools(
            agent=agent, tools=tools, verbose=verbose, callbacks=callbacks, **kwargs
        )
        return ChainExecutor(chain=agent_executor)

    def make_agent(self):
        # TOOLS
        tools = get_tools(callback=self.callback_handler)

        # PLANNER
        planner = load_chat_planner(self.llm, system_prompt=hub.pull("kastanday/ml4bio-rnaseq-planner").format(user_info=get_user_info_string))

        # EXECUTOR
        # executor = load_agent_executor(self.llm, tools, verbose=True, trim_intermediate_steps=fancier_trim_intermediate_steps, handle_parsing_errors=True)
        executor = self.custom_load_agent_executor(self.llm, tools, verbose=True, callbacks=[self.callback_handler], handle_parsing_errors=True)

        # Create PlanAndExecute Agent
        workflow_agent = PlanAndExecute(planner=planner, executor=executor, verbose=True, callbacks=[self.callback_handler])

        return workflow_agent
