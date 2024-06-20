import os
from injector import inject
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from ai_ta_backend.database.poi_sql import POISQLDatabase
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_community.utilities.sql_database import SQLDatabase


from langchain_openai import ChatOpenAI


from langchain.tools import tool, StructuredTool
from langgraph.prebuilt.tool_executor import ToolExecutor


from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage

from langgraph.prebuilt import ToolInvocation
import json
from langchain_core.messages import FunctionMessage
from langchain_core.utils.function_calling import convert_to_openai_function
from langgraph.graph import StateGraph, END

from ai_ta_backend.utils.agent_utils import generate_response_agent, initalize_sql_agent
import traceback

##### Setting up the Graph Nodes, Edges and message communication

class AgentState(TypedDict):
		messages: Annotated[Sequence[BaseMessage], operator.add]

class POIInput(BaseModel):
		input: str

@tool("plants_sql_tool", return_direct=True, args_schema=POIInput)
def generate_sql_query(input:str) -> str:
	"""Given a query looks for the three most relevant SQL sample queries"""
	user_question = input
	llm = ChatOpenAI(model="gpt-4o", temperature=0)
	### DATABASE
	db = SQLDatabase.from_uri(f"sqlite:///{os.environ['POI_SQL_DB_NAME']}")
	sql_agent = initalize_sql_agent(llm, db)
	response = generate_response_agent(sql_agent,user_question)
	return response['output']

class POIAgentService:
	@inject
	def __init__(self, poi_sql_db: POISQLDatabase):
			self.poi_sql_db = poi_sql_db
			self.model = ChatOpenAI(model="gpt-4o", temperature=0)
			# self.tools = [StructuredTool.from_function(self.generate_sql_query, name="Run SQL Query", args_schema=POIInput)]
			self.tools = [generate_sql_query]
			self.tool_executor = ToolExecutor(self.tools)
			self.functions = [convert_to_openai_function(t) for t in self.tools]
			self.model = self.model.bind_functions(self.functions)
			self.workflow = self.initialize_workflow(self.model)


	
	# Define the function that determines whether to continue or not
	def should_continue(self, state):
			messages = state['messages']
			last_message = messages[-1]
			# If there is no function call, then we finish
			if "function_call" not in last_message.additional_kwargs:
					return "end"
			# Otherwise if there is, we continue
			else:
					return "continue"

	# Define the function that calls the model
	def call_model(self, state):
			messages = state['messages']
			response = self.model.invoke(messages)
			# We return a list, because this will get added to the existing list
			return {"messages": [response]}

	# Define the function to execute tools
	def call_tool(self, state):
			messages = state['messages']
			# Based on the continue condition
			# we know the last message involves a function call
			last_message = messages[-1]
			# We construct an ToolInvocation from the function_call
			action = ToolInvocation(
					tool=last_message.additional_kwargs["function_call"]["name"],
					tool_input=json.loads(last_message.additional_kwargs["function_call"]["arguments"]),
			)
			print(f"The agent action is {action}")
			# We call the tool_executor and get back a response
			response = self.tool_executor.invoke(action)
			print(f"The tool result is: {response}")
			# We use the response to create a FunctionMessage
			function_message = FunctionMessage(content=str(response), name=action.tool)
			# We return a list, because this will get added to the existing list
			return {"messages": [function_message]}

	def initialize_workflow(self, agent):
			workflow = StateGraph(AgentState)
			workflow.add_node("agent", self.call_model)
			workflow.add_node("action", self.call_tool)
			workflow.set_entry_point("agent")
			workflow.add_conditional_edges(
					"agent",
					self.should_continue,
					{
							"continue": "action",
							"end": END
					}
			)
			workflow.add_edge('action', 'agent')
			return workflow.compile()
	
	def run_workflow(self, user_input):
		#agent = initialize_agent()
		try:
			
			output = self.workflow.invoke(user_input)
			return output
		except Exception as e:
			traceback.print_exc()
			return str(e)