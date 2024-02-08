from typing import Any, Dict, Union

import supabase
from langchain.agents import AgentType, initialize_agent, load_tools
from langchain.callbacks.base import BaseCallbackHandler
from langchain.llms import OpenAI
from langchain.schema import AgentAction, AgentFinish
import os


class MemoryCallbackHandler(BaseCallbackHandler):

  def __init__(self):
    self.tool_in_progress = False  # usage TBD

    self.supabase_client = supabase.create_client(  # type: ignore
        supabase_url=os.getenv('SUPABASE_URL'),  # type: ignore
        supabase_key=os.getenv('SUPABASE_API_KEY'))  # type: ignore

  def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> Any:
    print(f"on_tool_start {serialized}")
    self.tool_in_progress = True

  def on_tool_end(self, output: str, **kwargs: Any) -> Any:
    """Run when LLM errors."""
    print(f"On tool end: {output}")
    if self.tool_in_progress:
      self.tool_in_progress = False
      print(f"Tool output: {output}")

  def on_tool_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> Any:
    """Run when LLM errors."""
    pass

  def on_llm_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> Any:
    """Run when LLM errors."""
    pass

  def on_agent_action(self, action: AgentAction, **kwargs: Any) -> Any:
    print(f"on_agent_action {action}")

  def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> Any:
    print(f"on_agent_finish {finish}")

  # def on_llm_start(
  #     self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
  # ) -> Any:
  #     print(f"on_llm_start {serialized}")

  # def on_llm_new_token(self, token: str, **kwargs: Any) -> Any:
  #     print(f"on_new_token {token}")

  # def on_chain_start(
  #     self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
  # ) -> Any:
  #     print(f"on_chain_start {serialized['name']}")


if __name__ == "__main__":
  # just for testing
  handler1 = MemoryCallbackHandler()

  llm = OpenAI(temperature=0, streaming=True)
  tools = load_tools(["llm-math"], llm=llm)
  agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)

  # Callbacks for handler1 will be issued by every object involved in the
  # Agent execution (llm, llmchain, tool, agent executor)
  agent.run("What is 2 raised to the 0.235 power?", callbacks=[handler1])
