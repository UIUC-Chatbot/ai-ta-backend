from typing import Dict, Union, Any, List

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import AgentAction, AgentFinish
from langchain.agents import AgentType, initialize_agent, load_tools
from langchain.callbacks import tracing_enabled
from langchain.llms import OpenAI
from langchain import hub
from .webhooks import get_langsmith_supabase


class MemoryCallbackHandler(BaseCallbackHandler):
    def __init__(self):
        self.tool_in_progress = False  # usage TBD

        self.supabase_client, self.langsmith_run_id = get_langsmith_supabase()

    def is_langsmith_run_id(self) -> bool:
        result = self.supabase_client.table("docker_images").select("langsmith_id").\
                                        eq("langsmith_id", self.langsmith_run_id).execute()
        return len(result["data"]) > 0

    def on_tool_start(
            self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> Any:
        print(f"on_tool_start {serialized}")
        if self.is_langsmith_run_id():
            self.supabase_client.table("docker_images").update({"on_tool_start": str(serialized)}).\
                                        eg("langsmith_id", self.langsmith_run_id).execute()
        else:
            self.supabase_client.table("docker_images").upsert(
                {"langsmith_id": self.langsmith_run_id, "on_tool_start": str(serialized)}).execute()
        self.tool_in_progress = True

    def on_tool_end(
            self, output: str, **kwargs: Any
    ) -> Any:
        """Run when LLM errors."""
        print(f"On tool end: {output}")
        if self.is_langsmith_run_id():
            self.supabase_client.table("docker_images").update({"on_tool_end": str(output)}).\
                                        eg("langsmith_id", self.langsmith_run_id).execute()
        else:
            self.supabase_client.table("docker_images").upsert(
                {"langsmith_id": self.langsmith_run_id, "on_tool_end": str(output)}).execute()

        if self.tool_in_progress:
            self.tool_in_progress = False
            print(f"Tool output: {output}")

    def on_tool_error(
            self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> Any:
        """Run when LLM errors."""
        pass

    def on_llm_error(
            self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> Any:
        """Run when LLM errors."""
        pass

    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> Any:
        print(f"on_agent_action {action}")
        if self.is_langsmith_run_id():
            self.supabase_client.table("docker_images").update({"on_agent_action": str(action)}).\
                                        eg("langsmith_id", self.langsmith_run_id).execute()
        else:
            self.supabase_client.table("docker_images").upsert(
                {"langsmith_id": self.langsmith_run_id, "on_agent_action": str(action)}).execute()

    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> Any:
        print(f"on_agent_finish {finish}")
        if self.is_langsmith_run_id():
            self.supabase_client.table("docker_images").update({"on_agent_finish": str(finish)}).\
                                        eg("langsmith_id", self.langsmith_run_id).execute()
        else:
            self.supabase_client.table("docker_images").upsert(
                {"langsmith_id": self.langsmith_run_id, "on_agent_finish": str(finish)}).execute()

    # def on_llm_start(
    #     self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    # ) -> Any:
    #     print(f"on_llm_start {serialized}")

    # def on_llm_new_token(self, token: str, **kwargs: Any) -> Any:
    #     print(f"on_new_token {token}")

    def on_chain_start(
            self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> Any:
        print(f"on_chain_start {serialized}")
        if self.is_langsmith_run_id():
            self.supabase_client.table("docker_images").update({"on_chain_start": str(serialized)}).\
                                        eg("langsmith_id", self.langsmith_run_id).execute()
        else:
            self.supabase_client.table("docker_images").upsert(
                {"langsmith_id": self.langsmith_run_id, "on_chain_start": str(serialized)}).execute()


def get_memory_callback_handler():
    handler = MemoryCallbackHandler()
    return handler


if __name__ == "__main__":
    # for testing
    handler1 = MemoryCallbackHandler()

    memory_prompt = hub.pull("kastanday/memory_manager_agent")

    llm = OpenAI(temperature=0, streaming=True)
    tools = load_tools(["llm-math"], llm=llm)
    agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)

    # Callbacks for handler1 will be issued by every object involved in the
    # Agent execution (llm, llmchain, tool, agent executor)
    agent.run("What is 2 raised to the 0.235 power?", callbacks=[handler1])
