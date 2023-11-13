## Memory management class
from langchain.llms import OpenAI
from langchain.chains import ConversationChain
from langchain.tools.base import Tool
from langchain.schema import BaseMemory
from pydantic import BaseModel
from typing import List, Dict, Any



class MemoryManager(BaseMemory, BaseModel):
    """
    Custom memory class for agents. Stores the following:
    - previous_steps: List[str] = []
    - current_step: str = ""
    - agent_scratchpad: str = ""
    - objective: str = ""
    - inputs: Dict[str, Any] = {}
    - outputs: Dict[str, Any] = {}
    Has tools for following functions:
    - edit_memory: edit any of the above variables
    - edit_memory_append: append to any of the above variables
    - edit_memory_replace: replace in any of the above variables

    """
    previous_steps: List[str] = []
    current_step: str = ""
    agent_scratchpad: str = ""
    objective: str = ""
    inputs: Dict[str, Any] = {}
    outputs: Dict[str, Any] = {}

    def clear(self):
        self.previous_steps = []
        self.current_step = ""
        self.agent_scratchpad = ""
        self.objective = ""
        self.inputs = {}
        self.outputs = {}

    def memory_variables(self) -> List[str]:
        return ["previous_steps", "current_step", "agent_scratchpad", "objective", "inputs", "outputs"]

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "previous_steps": self.previous_steps,
            "current_step": self.current_step,
            "agent_scratchpad": self.agent_scratchpad,
            "objective": self.objective,
            "inputs": self.inputs,
            "outputs": self.outputs
        }

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        self.previous_steps.append(self.current_step)
        self.current_step = inputs["current_step"]
        self.agent_scratchpad = outputs["output"]
        self.objective = inputs["objective"]
        self.inputs = inputs
        self.outputs = outputs

    def edit_memory(self, key, content):
        if key in self.memory_variables():
            setattr(self, key, content)
        else:
            raise Exception("Invalid key")

    def edit_memory_append(self, key, content):
        if key in self.memory_variables():
            getattr(self, key).append(content)
        else:
            raise Exception("Invalid key")

    def edit_memory_replace(self, key, old_content, new_content):
        if key in self.memory_variables():
            getattr(self, key).replace(old_content, new_content)
        else:
            raise Exception("Invalid key")

    def memory_tools(self, key=None, content=None, old_content=None, new_content=None) -> dict:
        """Returns a dict of available memory functions."""

        tools = [
            Tool.from_function(
                func=self.edit_memory(key, content),
                name="Edit Memory",
                description="Edit memory.key <= content",
            ),
            Tool.from_function(
                func=self.edit_memory_append(key, content),
                name="Edit Memory Append",
                description="Append to memory.key <= content",
            ),
            Tool.from_function(
                func=self.edit_memory_replace(key, old_content, new_content),
                name="Edit Memory Replace",
                description="Replace in memory.key[old_content] <= new_content",
            ),
        ]

        return tools
