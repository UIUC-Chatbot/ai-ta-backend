import supabase
import pandas as pd
import os
from typing import List
import tiktoken

def get_cost(course_name: str)-> List:
    """
    Args: 
      course_name: UIUC.chat course name
    Returns:
      List: [total_queries, total_cost, avg_cost] for the given course
    """
    print("Getting cost for course: ", course_name)
    # initialize supabase
    supabase_client = supabase.create_client(supabase_url=os.getenv('SUPABASE_URL'), 
                                             supabase_key=os.getenv('SUPABASE_API_KEY'))
    
    response = supabase_client.table("llm-convo-monitor").select("*").eq("course_name", course_name).execute()
    data = response.data
    df = pd.DataFrame(data)
    convo_df = df['convo']

    total_queries = 0
    list_of_prompt_costs = []
    list_of_prompt_token_lengths = []



    for row in convo_df:
        
        messages = row['messages']
        model_name = row['model']['id']
        prompt = row['prompt']
        for message in messages:
            content = message['content']
            if message['role'] == 'user': 
                # prompt cost
                total_queries += 1
                query_cost, query_tokens = get_tokens_and_cost(content, prompt, model_name)
                list_of_prompt_costs.append(query_cost)
                list_of_prompt_token_lengths.append(query_tokens)
            else:
                # completion cost
                pass

    total_course_cost = round(sum(list_of_prompt_costs), 4)
    avg_course_cost = round(total_course_cost/total_queries, 4)

    print("Total queries: ", total_queries)
    print("Total tokens: ", round(sum(list_of_prompt_token_lengths), 4))
    print("Total cost: ", total_course_cost)
    print("Average cost: ", avg_course_cost)

    return [total_queries, total_course_cost, avg_course_cost]

def get_tokens_and_cost(query: str, std_prompt: str, model_name: str):
    """
    Takes an input query and returns the cost.
    1. Cost of encoding query + prompt
    """
    # initialize tokenizer
    tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")
    if model_name.startswith('gpt-4'):
        # 8k context
        prompt_cost_per_token: float = 0.03/1000
        completion_cost_per_token: float = 0.06/1000

        # 32k context
        # prompt_cost_per_token: float = 0.06/1000
        # completion_cost_per_token: float = 0.12/1000

    elif model_name.startswith('gpt-3.5-turbo'):
        # 4k context
        prompt_cost_per_token: float = 0.0015/1000
        completion_cost_per_token: float = 0.002/1000

        # 16k context
        # prompt_cost_per_token: float = 0.003/1000
        # completion_cost_per_token: float = 0.004/1000

    else:
        print(f"No idea of cost! Pricing not supported for model: `{model_name}`")

    # get cost of encoding query + prompt
    input_str = std_prompt + " " + query
    num_of_input_tokens = len(tokenizer.encode(input_str))
    prompt_cost = round(float(prompt_cost_per_token * num_of_input_tokens),4)

    return prompt_cost, num_of_input_tokens
