import tiktoken


def count_tokens_and_cost(prompt: str, completion: str = '', openai_model_name: str = "gpt-3.5-turbo") -> tuple[int, float] | tuple[int, float, int, float]:
  """
    Returns the number of tokens in a text string.
    
    Only the first parameter is required, a string of text to measure. THe completion and model name are optional.
    
    num_tokens, prompt_cost = num_tokens_from_string(prompt="hello there")
    num_tokens_prompt, prompt_cost, num_tokens_completion, completion_cost  = num_tokens_from_string(prompt="hello there", completion="how are you?")
    
    
    
  Args:
      prompt (str): _description_
      completion (str, optional): _description_. Defaults to ''.
      openai_model_name (str, optional): _description_. Defaults to "gpt-3.5-turbo".

  Returns:
      tuple[int, float] | tuple[int, float, int, float]: Returns the number of tokens consumed and the cost. The total cost you'll be billed is the sum of each individual cost (prompt_cost + completion_cost)
  """
    encoding = tiktoken.encoding_for_model(openai_model_name)
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
      print(f"NO IDEA OF COST, pricing not supported for model model: `{openai_model_name}`")
      prompt_token_cost = 0 
      completion_token_cost = 0
    
    if completion == '':
      num_tokens_prompt: int = len(encoding.encode(prompt))
      prompt_cost: float = prompt_token_cost * num_tokens_prompt
      return num_tokens_prompt, prompt_cost
    else:
      num_tokens_prompt: int = len(encoding.encode(prompt))
      num_tokens_completion: int = len(encoding.encode(completion))
      prompt_cost: float = prompt_token_cost * num_tokens_prompt
      completion_cost: float = completion_token_cost * num_tokens_prompt
      return num_tokens_prompt, prompt_cost, num_tokens_completion, completion_cost
