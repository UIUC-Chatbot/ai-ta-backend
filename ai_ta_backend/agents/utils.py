
import inspect
import traceback
from typing import List, Tuple

from langchain.schema import AgentAction

from ai_ta_backend.utils_tokenization import count_tokens_and_cost


def fancier_trim_intermediate_steps(steps: List[Tuple[AgentAction, str]]) -> List[Tuple[AgentAction, str]]:
  """
    Trim the history of Agent steps to fit within the token limit.
    If we're over the limit, start removing the logs from the oldest actions first. then remove the tool_input from the oldest actions. then remove the tool from the oldest actions. then remove the oldest actions entirely. To remove any of these, just set it as an empty string.

    Args:
        steps (List[Tuple[AgentAction, str]]): A list of agent actions and associated strings.

    Returns:
        List[Tuple[AgentAction, str]]: A list of the most recent actions that fit within the token limit.
    """
  try:
    def count_tokens(action: AgentAction) -> int:
      return sum(count_tokens_and_cost(str(getattr(action, attr)))[0] for attr in ['tool', 'tool_input', 'log'])

    token_limit = 4_000
    total_tokens = sum(count_tokens(action) for action, _ in steps)

    # Remove the logs if over the limit
    if total_tokens > token_limit:
      for action, _ in steps:
        action.log = ''
        total_tokens = sum(count_tokens(action) for action, _ in steps)
        if total_tokens <= token_limit:
          break

    # Remove the tool_input if over the limit
    if total_tokens > token_limit:
      for action, _ in steps:
        action.tool_input = ''
        total_tokens = sum(count_tokens(action) for action, _ in steps)
        if total_tokens <= token_limit:
          break

    # Remove the tool if over the limit
    if total_tokens > token_limit:
      for action, _ in steps:
        action.tool = ''
        total_tokens = sum(count_tokens(action) for action, _ in steps)
        if total_tokens <= token_limit:
          break

    # Remove the oldest actions if over the limit
    while total_tokens > token_limit:
      steps.pop(0)
      total_tokens = sum(count_tokens(action) for action, _ in steps)

    # print("In fancier_trim_latest_3_actions!! 👇👇👇👇👇👇👇👇👇👇👇👇👇👇 ")
    # print(steps)
    # print("Tokens used: ", total_tokens)
    # print("👆👆👆👆👆👆👆👆👆👆👆👆👆")
    return steps
  except Exception as e:
    print("-----------❌❌❌❌------------START OF ERROR-----------❌❌❌❌------------")
    print(f"Error in {inspect.currentframe().f_code.co_name}: {e}") # type: ignore # print function name in error.
    print(f"Traceback:")
    traceback.print_exc()
    return [steps[-1]]
