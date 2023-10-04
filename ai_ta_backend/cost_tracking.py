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
    list_of_response_costs = []
    list_of_response_token_lengths = []

    for row in convo_df:
        
        messages = row['messages']
        model_name = row['model']['id']
        prompt = row['prompt']
        for message in messages:
            content = message['content']
            if message['role'] == 'user': 
                # prompt cost
                total_queries += 1
                query_cost, query_tokens = get_tokens_and_cost(content, prompt, model_name, flag='query')
                list_of_prompt_costs.append(query_cost)
                list_of_prompt_token_lengths.append(query_tokens)
            else:
                # completion cost
                response_cost, response_tokens = get_tokens_and_cost(content, prompt, model_name, flag='response')
                list_of_response_costs.append(response_cost)
                list_of_response_token_lengths.append(response_tokens)

    # total cost = prompt cost + response cost
    total_course_cost = round(sum(list_of_prompt_costs) + sum(list_of_response_costs), 4)
    avg_course_cost = round(total_course_cost/total_queries, 4)

    print("Total queries: ", total_queries)
    print("Total prompt tokens: ", round(sum(list_of_prompt_token_lengths), 4))
    print("Total response tokens: ", round(sum(list_of_response_token_lengths), 4))
    print("Total prompt cost: ", round(sum(list_of_prompt_costs), 4))
    print("Total response cost: ", round(sum(list_of_response_costs), 4))
    print("Total cost: ", total_course_cost)
    print("Average cost: ", avg_course_cost)

    return [total_queries, total_course_cost, avg_course_cost]

def get_tokens_and_cost(text: str, std_prompt: str, model_name: str, flag: str = 'query'):
    """
    Takes an input query and returns the cost.
    1. Cost of encoding query + prompt
    2. Cost of answer generation by the model
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

    if flag == 'query':
        input_str = std_prompt + " " + text
        num_of_input_tokens = len(tokenizer.encode(input_str))
        prompt_cost = round(float(prompt_cost_per_token * num_of_input_tokens),4)
        return prompt_cost, num_of_input_tokens
    else:
        output_str = text
        num_of_output_tokens = len(tokenizer.encode(output_str))
        response_cost = round(float(completion_cost_per_token * num_of_output_tokens),4)
        return response_cost, num_of_output_tokens

    
