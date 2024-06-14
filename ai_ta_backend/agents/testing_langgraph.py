"""
USAGE:
python -m ai_ta_backend.agents.testing_langgraph
"""

import uuid

from dotenv import load_dotenv
from langchain import hub

from ai_ta_backend.agents.langrgraph_agent_v2 import PlanExecute
from ai_ta_backend.agents.langrgraph_agent_v2 import WorkflowAgent

load_dotenv(override=True)

# langchain.debug = True  # True for more detailed logs
# VERBOSE = True

import asyncio

if __name__ == '__main__':

  async def main():
    id = uuid.uuid4()
    a = WorkflowAgent(id)
    await a.run("Write a function to calculate the mean of a list of numbers.")

  asyncio.run(main())

# print("-------- OPENAI_API_BASE", os.environ['OPENAI_API_BASE'])
# print("-------- OPENAI_API_TYPE", os.environ['OPENAI_API_TYPE'])
# print("-------- AZURE_ENDPOINT", os.environ['AZURE_ENDPOINT'])


def stateToPrompt(state: PlanExecute, token_limit: int = 8_000):
  """
  Memory prompt: https://smith.langchain.com/hub/kastanday/memory_manager_agent
  Inputs = ['github_issue', 'messages_with_human', 'plan', 'tool_use_history']
  """
  prompt_template = hub.pull("kastanday/memory_manager_agent")
  print(prompt_template)

  # if

  return prompt_template.format(
      # user_info=get_user_info_string(),
      input=state['input'],
      chat_history='\n'.join([f"User: {message.content}" for message in state['chat_history']]),
      agent_outcome=state['response'],
      intermediate_steps='\n'.join([f"{action}: {observation}" for action, observation in state['past_steps']]),  # type: ignore
  )
