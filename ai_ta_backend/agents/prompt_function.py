from ai_ta_backend.agents.langgraph_agent import AgentState
from langchain import hub


def stateToPrompt(state: AgentState, token_limit: int = 8_000):
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
      agent_outcome=state['agent_outcome'],
      intermediate_steps='\n'.join([f"{action}: {observation}" for action, observation in state['intermediate_steps']]),
  )


if __name__ == '__main__':
  a = AgentState({
      'input': 'hello',
      'chat_history': [],
      'agent_outcome': None,
      'intermediate_steps': [],
      'plan': [],
  })
  print(a)
  ret = stateToPrompt(a)
  print(ret)
