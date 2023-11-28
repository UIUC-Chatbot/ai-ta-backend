## Memory management agent
## Not used yet. Will implement later.

from langchain.agents import Tool, AgentExecutor, LLMSingleActionAgent, AgentOutputParser
from langchain.prompts import StringPromptTemplate
from langchain.llms import OpenAI
from langchain.tools import tool
from langchain.utilities import SerpAPIWrapper
from langchain.chains import LLMChain
from typing import List, Union
from langchain.schema import AgentAction, AgentFinish, OutputParserException
import re

from ai_ta_backend.prompts.memgpt_prompt import get_memgpt_system_prompt


class MemoryManagementAgent():
    """
    This agent is used to manage memory of the system.
    """
    def __init__(self, llm: OpenAI, tools: List[Tool], verbose: bool = True, **kwargs):
        #super().__init__(llm, tools, verbose, **kwargs)
        self.llm = OpenAI(temperature=0)
        self.memory = None
        tools = self.get_tools()
        tool_names = [tool.name for tool in tools]
        llm_chain = LLMChain(llm=self.llm, tools=tools, verbose=verbose)
        self.mem_agent = LLMSingleActionAgent(llm_chain, allowed_tools=tool_names, verbose=verbose)

    def _get_prompt_template(self) -> StringPromptTemplate:
        return StringPromptTemplate(
        template="Memory Management Agent: {input}",
        input_variables=["input"],
        )

    def _get_output_parser(self) -> AgentOutputParser:
        return self._parser


    def get_tools(self) -> List[Tool]:
        return [
            Tool.from_function(
                func=self.edit_memory,
                name="edit_memory",
                description="Edit memory with current content"
            ),
            Tool.from_function(
                func=self.edit_memory_append,
                name="edit_memory_append",
                description="Appends to memory new content"
            ),
            Tool.from_function(
                func=self.edit_memory_replace,
                name="edit_memory_replace",
                description="Replaces memory based on content"
            ),
        ]

    @tool(name="memory_append")
    def memory_append(self, name, content):
        print("memory append")
        new_len = self.memory.edit_append(name, content)
        print("rebuild memory")
        self.rebuild_memory()
        print("done")
        return None

    @tool(name="memory_replace")
    def edit_memory_replace(self, name, old_content, new_content):
        new_len = self.memory.edit_replace(name, old_content, new_content)
        self.rebuild_memory()
        return None

    @tool(name="memory_rebuild")
    def rebuild_memory(self):
        """Rebuilds the system message with the latest memory object"""
        curr_system_message = self.messages[0]  # this is the system + memory bank, not just the system prompt
        new_system_message = get_memgpt_system_prompt(self.tools).format(input=curr_system_message["message"], intermediate_steps=[])

        # Store the memory change (if stateful)
        self.update_memory(self.memory)

        # Swap the system message out
        self.swap_system_message(new_system_message)
