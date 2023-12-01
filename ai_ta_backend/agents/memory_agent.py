# Agent to manage memory from the database
from utils import SupabaseDB
from langchain.tools import tool
from langchain.tools import StructuredTool
from langchain.agents import AgentType, initialize_agent, load_tools
from langchain.llms import OpenAI
from langchain.tools import BaseTool

TASK_PREFIX = """Check the previous steps and the current objective and change the memory object accordingly.
{objective}

"""


MEMORY_CONTEXT = """
Memory:
Tools used in chronological order(1 is oldest) : {tools_used}
Actions taken in chronological order(1 is oldest) : {agent_action_steps}
"""

def memory_agent(image_name=None):
    """Agent to manage memory from the database"""
    tools, actions = get_memory_from_db(table_name="docker_images", image_name=image_name)
    memory = Memory(tools=tools, actions=actions)
    available_functions = [edit_memory_tool, edit_append_memory_tool]
    llm = OpenAI(temperature=0, streaming=True)
    tools = load_tools([edit_memory_tool(memory), edit_append_memory_tool(memory)], llm=llm)
    agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)



@tool
def edit_memory_tool(memory: object, field: str = '', content: list = []):
    """Tool to manage memory"""
    memory.edit(field, content)

@tool
def edit_append_memory_tool(memory: object, field: str = '', content: list = []):
    memory.edit_append(field, content)


def get_memory_from_db(table_name: str, image_name: str):
    db = SupabaseDB(table_name=table_name, image_name=image_name)
    tools, actions = [], []

    if db.is_exists_image():
        tool_data = db.fetch_field_from_db("on_tool_start")
        if tool_data:
            tools = [item['name'] for item in tool_data]

        action_data = db.fetch_field_from_db("on_agent_action")
        if action_data:
            actions = [item['log'] for item in action_data]

    return tools, actions


class Memory:
    def __init__(self, tools: list, actions: list):
        self.tools = tools  # list of tools used
        self.actions = actions   # list of actions taken by the agent

    def get_memory_context(self):
        if self.tools:
            tools_used = ", ".join(self.tools)
        if self.actions:
            actions_taken = ", ".join(self.actions)
        return MEMORY_CONTEXT.format(
            tools_used=tools_used,
            agent_action_steps=actions_taken,
        )

    def edit(self, field: str, content: list):
        if field == "tools":
            self.tools = content
        elif field == "actions":
            self.actions = content
        else:
            raise ValueError(f"Invalid field: {field}")

    def edit_append(self, field: str, content: list):
        if field == "tools":
            self.tools.append(content)
        elif field == "actions":
            self.actions.append(content)
        else:
            raise ValueError(f"Invalid field: {field}")





class MemoryToolSelection(BaseTool):
    name = "Memory Tool Selection"
    description = "Select a tool to manage memory. Options: edit_memory_tool, edit_append_memory_tool"


