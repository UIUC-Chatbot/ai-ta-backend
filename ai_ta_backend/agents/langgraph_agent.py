from langchain_community.tools.tavily_search import TavilySearchResults
import getpass
import os
import platform

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolExecutor
from typing import TypedDict, Annotated, Union
import operator
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from langchain import hub
from langchain.chat_models import AzureChatOpenAI, ChatOpenAI
from langchain_experimental.plan_and_execute import (PlanAndExecute,
                                                     load_agent_executor,
                                                     load_chat_planner)
from ai_ta_backend.agents.tools import get_tools
from ai_ta_backend.agents.utils import fancier_trim_intermediate_steps

load_dotenv(override=True)


def get_user_info_string():
  username = getpass.getuser()
  current_working_directory = os.getcwd()
  operating_system = platform.system()
  default_shell = os.environ.get("SHELL")

  return f"[User Info]\nName: {username}\nCWD: {current_working_directory}\nSHELL: {default_shell}\nOS: {operating_system}"


class AgentState(TypedDict):
    # The input string
    input: str
    # The list of previous messages in the conversation
    chat_history: list[BaseMessage]
    # The outcome of a given call to the agent
    # Needs `None` as a valid type, since this is what this will start as
    agent_outcome: Union[AgentAction, AgentFinish, None]
    # List of actions and corresponding observations
    # Here we annotate this with `operator.add` to indicate that operations to
    # this state should be ADDED to the existing values (not overwrite it)
    intermediate_steps: Annotated[list[tuple[AgentAction, str]], operator.add]


class WorkflowAgent:
    def __init__(self, langsmith_run_id):
        self.langsmith_run_id = langsmith_run_id
        if os.environ['OPENAI_API_TYPE'] == 'azure':
            self.llm = AzureChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=3, request_timeout=60 * 3,
                                       deployment_name=os.environ['AZURE_OPENAI_ENGINE'],
                                       streaming=True)  # type: ignore
        else:
            self.llm: ChatOpenAI = ChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=500,
                                              request_timeout=60 * 3, streaming=True)  # type: ignore
        self.tools = get_tools(langsmith_run_id=self.langsmith_run_id)
        self.agent = self.make_agent()


    def make_agent(self):
        # PLANNER
        planner = load_chat_planner(self.llm, system_prompt=hub.pull("kastanday/ml4bio-rnaseq-planner").format(
                                    user_info=get_user_info_string))

        # EXECUTOR
        executor = load_agent_executor(self.llm, self.tools, verbose=True,
                                       trim_intermediate_steps=fancier_trim_intermediate_steps,
                                       handle_parsing_errors=True)
        # executor = load_agent_executor(self.llm, tools, verbose=True, handle_parsing_errors=True)

        # Create PlanAndExecute Agent
        workflow_agent = PlanAndExecute(planner=planner, executor=executor, verbose=True)

        return workflow_agent

    # Invoke the agent
    def execute_agent(self, data):
        agent_outcome = self.agent.invoke(data, {
                    "metadata": {"langsmith_run_id": str(self.langsmith_run_id)}})
        return {"agent_outcome": agent_outcome}

    # Define the function to execute tools
    def execute_tools(self, data):
        # Get the most recent agent_outcome - this is the key added in the `agent` above
        agent_action = data['agent_outcome']
        tool_executor = ToolExecutor(self.tools)
        output = tool_executor.invoke(agent_action)
        return {"intermediate_steps": [(agent_action, str(output))]}

    # Define logic that will be used to determine which conditional edge to go down
    def should_continue(self, data):
        # The return string will be used when setting up the graph to define the flow
        # If the agent outcome is an AgentFinish, then we return `exit` string
        if isinstance(data['agent_outcome'], AgentFinish):
            return "end"
        # Otherwise, an AgentAction is returned. Return `continue` string
        else:
            return "continue"

    def run(self, input_prompt):
        # Define a new graph
        workflow = StateGraph(AgentState)

        # Define the two nodes we will cycle between
        workflow.add_node("agent", self.execute_agent)
        workflow.add_node("action", self.execute_tools)

        # Set the entrypoint as `agent`
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            # First, we define the start node. We use `agent`.
            # This means these are the edges taken after the `agent` node is called.
            "agent",
            # Next, we pass in the function that will determine which node is called next.
            self.should_continue,
            # Pass in a mapping. The keys are strings, and the values are other nodes.
            # END is a special node marking that the graph should finish.
            # The output of `should_continue`, will be matched against this mapping and the respective node is called
            {
                # If `tools`, then we call the tool node.
                "continue": "action",
                # Otherwise we finish.
                "end": END
            }
        )

        # Add a normal edge from `tools` to `agent`. This means that after `tools` is called, `agent` node is called next.
        workflow.add_edge('action', 'agent')
        app = workflow.compile()

        key, value = '', ''
        inputs = {"input": input_prompt, "chat_history": [], "intermediate_steps": []}
        for output in app.stream(inputs):
            # stream() yields dictionaries with output keyed by node name
            for key, value in output.items():
                print(f"Output from node '{key}':")
                print("---")
                print(value)
            print("\n---\n")

        result = key + value
        return result
