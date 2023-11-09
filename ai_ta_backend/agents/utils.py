
import inspect
import logging
import os
import time
import traceback
import uuid
from typing import List, Tuple

import langsmith
import ray
from langchain.schema import AgentAction
from langsmith import Client
from langsmith.schemas import Run
import tiktoken


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
    
    # for logging
    original_total_tokens = sum(count_tokens(action) for action, _ in steps)
    original_steps = steps.copy()

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

    log = Log(message=f"trim_intermediate_steps", 
      original_steps=str(original_steps),
      final_steps=str(steps),
      original_tokens=original_total_tokens,
      final_tokens=total_tokens,
    )
    response = log_client.send(log)
    response.raise_for_status()

    return steps
  except Exception as e:
    print("-----------❌❌❌❌------------START OF ERROR-----------❌❌❌❌------------")
    print(f"Error in {inspect.currentframe().f_code.co_name}: {e}") # type: ignore # print function name in error.
    print(f"Traceback:")
    traceback.print_exc()
    return [steps[-1]]

def get_langsmit_run_from_metadata(metadata_value, metadata_key="run_id_in_metadata") -> langsmith.schemas.Run:
  """This will only return the FIRST match on single metadta field

  Args:
      metadata_key (str, optional): _description_. Defaults to "run_id_in_metadata".
      metadata_value (str, optional): _description_. Defaults to "b187061b-afd7-40ab-a918-705cf16219c3".

  Returns:
      Run: _description_
  """
  langsmith_client = Client()
  runs = langsmith_client.list_runs(project_name=os.environ['LANGCHAIN_PROJECT'])

  count = 0
  for r in runs: 
    count += 1
  print(f"Found num runs: {count}")

  for run in langsmith_client.list_runs(project_name=os.environ['LANGCHAIN_PROJECT']):
    if run.extra and run.extra.get('metadata') and run.extra.get('metadata').get(metadata_key) == metadata_value:
      # return the 'top-level' of the trace (keep getting runs' parents until at top)
      if run.parent_run_id:
        curr_run = run
        while curr_run.parent_run_id:
          curr_run = langsmith_client.read_run(str(curr_run.parent_run_id))
        return curr_run
      else: 
        return run

def get_langsmith_trace_sharable_url(run_id_in_metadata, project_name='', time_delay_s=0):
  """

  Adding metadata to runs: https://docs.smith.langchain.com/tracing/tracing-faq#how-do-i-add-metadata-to-runs
  
  Background: 
    A 'Trace' is a collection of runs organized in a tree or graph. The 'Root Run' is the top level run in a trace.
  https://docs.smith.langchain.com/tracing/tracing-faq

  Args:
      project (_type_): _description_
  """
  time.sleep(time_delay_s)
  if project_name == '':
    project_name = os.environ['LANGCHAIN_PROJECT']
  
  langsmith_client = Client()

  # re-attempt to find the run, maybe it hasn't started yet.
  run = None
  for i in range(8):
    run = get_langsmit_run_from_metadata(str(run_id_in_metadata), metadata_key="run_id_in_metadata")
    if run is not None: 
      break
    time.sleep(5)

  if run is None:
    return f"Failed to generate sharable URL, cannot find this run on LangSmith. RunID: {run_id_in_metadata}"

  if not langsmith_client.run_is_shared(run.id):
    sharable_url = langsmith_client.share_run(run_id=run.id)
  else:
    sharable_url = langsmith_client.read_run_shared_link(run_id=run.id)
  logging.info(f'⭐️ sharable_url: {sharable_url}')
  return sharable_url

def count_tokens_and_cost(prompt: str, completion: str = '', openai_model_name: str = "gpt-3.5-turbo"): # -> tuple[int, float] | tuple[int, float, int, float]:
  """
  Returns the number of tokens in a text string.

  Only the first parameter is required, a string of text to measure. The completion and model name are optional.

  num_tokens, prompt_cost = count_tokens_and_cost(prompt="hello there")
  num_tokens_prompt, prompt_cost, num_tokens_completion, completion_cost  = count_tokens_and_cost(prompt="hello there", completion="how are you?")  
  
  Args:
      prompt (str): _description_
      completion (str, optional): _description_. Defaults to ''.
      openai_model_name (str, optional): _description_. Defaults to "gpt-3.5-turbo".

  Returns:
      tuple[int, float] | tuple[int, float, int, float]: Returns the number of tokens consumed and the cost. The total cost you'll be billed is the sum of each individual cost (prompt_cost + completion_cost)
  """
  # encoding = tiktoken.encoding_for_model(openai_model_name)
  openai_model_name = openai_model_name.lower()
  encoding = tiktoken.encoding_for_model("gpt-3.5-turbo") # I think they all use the same encoding
  prompt_cost = 0
  completion_cost = 0
  
  prompt_token_cost = 0 
  completion_token_cost = 0
  
  if openai_model_name.startswith("gpt-3.5-turbo"):
    if "16k" in openai_model_name:
      prompt_token_cost: float = 0.003 / 1_000
      completion_token_cost: float = 0.004 / 1_000
    else:
      # 3.5-turbo regular (4k context)
      prompt_token_cost: float = 0.0015 / 1_000
      completion_token_cost: float = 0.002 / 1_000
      
  elif openai_model_name.startswith("gpt-4"):
    if "32k" in openai_model_name:
      prompt_token_cost = 0.06 / 1_000
      completion_token_cost = 0.12 / 1_000
    else:
      # gpt-4 regular (8k context)
      prompt_token_cost = 0.03 / 1_000
      completion_token_cost = 0.06 / 1_000
  elif openai_model_name.startswith("text-embedding-ada-002"):
    prompt_token_cost = 0.0001 / 1_000
    completion_token_cost = 0.0001 / 1_000
  else: 
    # no idea of cost
    print(f"NO IDEA OF COST, pricing not supported for model model: `{openai_model_name}`. (Defaulting to GPT-4 pricing...)")
    prompt_token_cost = 0.03 / 1_000
    completion_token_cost = 0.06 / 1_000
  
  if completion == '':
    num_tokens_prompt: int = len(encoding.encode(prompt))
    prompt_cost = float(prompt_token_cost * num_tokens_prompt)
    return num_tokens_prompt, prompt_cost
  elif prompt == '':
    num_tokens_completion: int = len(encoding.encode(completion))
    completion_cost = float(completion_token_cost * num_tokens_completion)
    return num_tokens_completion, completion_cost
  else:
    num_tokens_prompt: int = len(encoding.encode(prompt))
    num_tokens_completion: int = len(encoding.encode(completion))
    prompt_cost = float(prompt_token_cost * num_tokens_prompt)
    completion_cost = float(completion_token_cost * num_tokens_completion)
    return num_tokens_prompt, prompt_cost, num_tokens_completion, completion_cost



import os

from newrelic_telemetry_sdk import Log, LogClient, Span, SpanClient

# from dotenv import load_dotenv

# load_dotenv(override=True)

log_client = LogClient(os.environ['NEW_RELIC_LICENSE_KEY'])

# log = Log(message="Message with metadata", **{'complex_metadata': 69.420, 'number_entry': 12, 'boolean_entry': False})

# log = Log(message="Message with metadata",
#           complex_metadata=69.420, 
#           number_entry=12, 
#           boolean_entry=False)
# response = log_client.send(log)
# response.raise_for_status()
# print("Log sent successfully 2!")


# Spans provide an easy way to time components of your code. The example code assumes you’ve set the following environment variables:
# with Span(name="sleep") as span:
#     time.sleep(0.5)

# span_client = SpanClient(os.environ["NEW_RELIC_LICENSE_KEY"])
# response = span_client.send(span)
# response.raise_for_status()
# print("Span sleep sent successfully!")