from typing import Dict, Union, Any, List

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import AgentAction, AgentFinish
from langchain.agents import AgentType, initialize_agent, load_tools
from langchain.callbacks import tracing_enabled
from langchain.llms import OpenAI
from langchain import hub
from ai_ta_backend.agents.utils import get_supabase_client, get_langsmith_id


class CustomCallbackHandler(BaseCallbackHandler):
    """A callback handler that stores the LLM's context and action in memory."""
    def __init__(self, run_id=None, image_name=None):
        self.tool_in_progress = False  # usage TBD

        self.supabase_client = get_supabase_client()
        if run_id:
            self.langsmith_run_id = run_id
        else:
            self.langsmith_run_id = get_langsmith_id()

        if image_name:
            self.image_name = image_name
        else:
            self.image_name = None

    def is_exists_image(self) -> bool:
        langsmith_response = self.supabase_client.table("docker_images").select("image_name").\
                                        eq("image_name", self.image_name).execute()
        return len(langsmith_response.data) > 0

    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> Any:
        print(f"on_tool_start {serialized}")
        if self.is_exists_image():
            response = self.supabase_client.table("docker_images").update({"on_tool_start": str(serialized)}).\
                                        eq("image_name", self.image_name).execute()
        else:
            response = self.supabase_client.table("docker_images").upsert(
                {"langsmith_id": self.langsmith_run_id, "image_name": self.image_name, "on_tool_start": str(serialized)}).execute()
        self.tool_in_progress = True
        print(response.data)

    def on_tool_end(self, output: str, **kwargs: Any) -> Any:
        """Run when LLM errors."""
        print(f"On tool end: {output}")
        if self.is_exists_image():
            response = self.supabase_client.table("docker_images").update({"on_tool_end": str(output)}).\
                                        eq("image_name", self.image_name).execute()
        else:
            response = self.supabase_client.table("docker_images").upsert(
                {"langsmith_id": self.langsmith_run_id, "image_name": self.image_name, "on_tool_end": str(output)}).execute()

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
        if self.is_exists_image():
            self.supabase_client.table("docker_images").update({"on_agent_action": str(action)}).\
                                        eq("image_name", self.image_name).execute()
        else:
            self.supabase_client.table("docker_images").upsert(
                {"langsmith_id": self.langsmith_run_id, "image_name": self.image_name, "on_agent_action": str(action)}).execute()

    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> Any:
        print(f"on_agent_finish {finish}")
        if self.is_exists_image():
            self.supabase_client.table("docker_images").update({"on_agent_finish": str(finish)}).\
                                        eq("image_name", self.image_name).execute()
        else:
            self.supabase_client.table("docker_images").upsert(
                {"langsmith_id": self.langsmith_run_id, "image_name": self.image_name, "on_agent_finish": str(finish)}).execute()

    # def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> Any:
    #     print(f"on_llm_start {serialized}")

    # def on_llm_new_token(self, token: str, **kwargs: Any) -> Any:
    #     print(f"on_new_token {token}")

    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any) -> Any:
        print("on_chain_start")
        if self.is_exists_image():
            self.supabase_client.table("docker_images").update({"on_chain_start": str(serialized)}).\
                                        eq("image_name", self.image_name).execute()
        else:
            self.supabase_client.table("docker_images").upsert(
                {"langsmith_id": self.langsmith_run_id, "image_name": self.image_name, "on_chain_start": str(serialized)}).execute()


def get_custom_callback_handler():
    handler = CustomCallbackHandler()
    return handler


if __name__ == "__main__":
    # for testing
    handler1 = CustomCallbackHandler()

    memory_prompt = hub.pull("kastanday/memory_manager_agent")

    llm = OpenAI(temperature=0, streaming=True)
    tools = load_tools(["llm-math"], llm=llm)
    agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)

    # Callbacks for handler1 will be issued by every object involved in the
    # Agent execution (llm, llmchain, tool, agent executor)
    agent.run("What is 2 raised to the 0.235 power?", callbacks=[handler1])
