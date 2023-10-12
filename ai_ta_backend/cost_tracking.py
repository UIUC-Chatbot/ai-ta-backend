import supabase
import pandas as pd
import os
from typing import List
import tiktoken
from datetime import datetime, timedelta


def get_complete_cost_of_course(course_name: str)-> List:
    """
    Calculates prices of the entire course and adds them to the course table.
    """
    print("Getting cost for course: ", course_name)
    # initialize supabase
    supabase_client = supabase.create_client(supabase_url=os.getenv('SUPABASE_URL'), 
                                             supabase_key=os.getenv('SUPABASE_API_KEY'))

    try: 
        # # get IDs and count of conversations for the course
        # response = supabase_client.table("llm-convo-monitor").select("id", count='exact').eq("course_name", course_name).order('id', desc=False).execute()
        # total_count = response.count
        # id_data = response.data
        # # get the first conversation ID
        # min_id = id_data[0]['id']
        # current_items = []
        # print("Total count: ", total_count)
        # print("First ID: ", min_id)

        # # get conversations in batches of 25
        # while len(current_items) < total_count:
        #     try:
        #         if len(current_items) == 0: # first iteration
        #             response = supabase_client.table("llm-convo-monitor").select("id, convo", count='exact').eq("course_name", course_name).gte('id', min_id).order('id', desc=False).limit(25).execute()
        #         else:
        #             response = supabase_client.table("llm-convo-monitor").select("id, convo", count='exact').eq("course_name", course_name).gt('id', min_id).order('id', desc=False).limit(25).execute()
        #         current_items += response.data
        #         min_id = response.data[-1]['id']
        #         print("Length of current items: ", len(current_items))
        #     except Exception as e:
        #         print("Error in fetching conversations: ", e)
        #         break

        # # all data is in current_items here
        # print("Final length of current items: ", len(current_items))
        # convo_df = pd.DataFrame(current_items)
        # convo_df = convo_df['convo']
        # #print(convo_df.head())

        # total_queries = 0
        # list_of_prompt_costs = []
        # list_of_prompt_token_lengths = []
        # list_of_response_costs = []
        # list_of_response_token_lengths = []

        # for row in convo_df:
        
        #     messages = row['messages']
        #     model_id = row['model']['id']
        #     prompt = row['prompt']

        #     for message in messages:
        #         content = message['content']
                
        #         if message['role'] == 'user':
        #             # calculate prompt costs
        #             # adding context only to input (user) messages
        #             if 'contexts' in message:
        #                 contexts = message['contexts']
        #                 for context in contexts:
        #                     if 'text' in context: # some contexts don't have text
        #                         content = content + " " + context['text']

        #             total_queries += 1
        #             query_cost, query_tokens = get_tokens_and_cost(content, prompt, model_id, flag='query')
        #             list_of_prompt_costs.append(query_cost)
        #             list_of_prompt_token_lengths.append(query_tokens)
        #         else:
        #             # calculate response costs
        #             response_cost, response_tokens = get_tokens_and_cost(content, prompt, model_id, flag='response')
        #             list_of_response_costs.append(response_cost)
        #             list_of_response_token_lengths.append(response_tokens)
        # print("all costs collected")
        # # at this point, we have tokens and costs for all conversations
        # total_prompt_cost = round(sum(list_of_prompt_costs), 4)
        # total_response_cost = round(sum(list_of_response_costs), 4)
        # total_course_cost = round(sum(list_of_prompt_costs) + sum(list_of_response_costs), 4)
        # total_embeddings_cost = 0.0
        # total_tokens = sum(list_of_prompt_token_lengths) + sum(list_of_response_token_lengths)
        # print("total prompt cost: ", total_prompt_cost)
        # print("total response cost: ", total_response_cost)
        # print("total course cost: ", total_course_cost)
        # print("total queries: ", total_queries)
        # print("total prompt tokens: ", sum(list_of_prompt_token_lengths))
        # print("total response tokens: ", sum(list_of_response_token_lengths))
        # print("total tokens: ", total_tokens)
        # print("-------------------------------------")

        # get costs for all time
        all_time_costs = get_course_cost(course_name, days=0)
        print("All time costs: ", all_time_costs)
        print("-------------------------------------")
        past_n_days_cost = get_course_cost(course_name, days=30)
        print("Past 30 days costs: ", past_n_days_cost)
        print("\n\n\n")
        

        # add the costs to the table
        response = supabase_client.table("uiuc-course-table").select("*").eq("course_name", course_name).execute()

        if len(response.data) == 0:
            # entry does not exist, insert new row
            print("Course entry does not exist. Creating a new entry...")
            insert_data, count = supabase_client.table("uiuc-course-table").insert([{"total_tokens": all_time_costs['total_tokens'], 
                                                                                     "total_prompt_price": all_time_costs['total_prompt_price'],
                                                                                     "total_completions_price": all_time_costs['total_completions_price'],
                                                                                     "total_embeddings_price": all_time_costs['total_embeddings_price'],
                                                                                     "total_queries": all_time_costs['total_queries'],
                                                                                     "course_name": course_name}]).execute()

        else: 
            # entry exists, update the row
            print("Course entry exists. Updating the entry...")
            update_data, count = supabase_client.table("uiuc-course-table").update([{"total_tokens": all_time_costs['total_tokens'], 
                                                                                     "total_prompt_price": all_time_costs['total_prompt_price'],
                                                                                     "total_completions_price": all_time_costs['total_completions_price'],
                                                                                     "total_embeddings_price": all_time_costs['total_embeddings_price'],
                                                                                     "total_queries": all_time_costs['total_queries']}]).eq("course_name", course_name).execute()
        return "Success!"
    except Exception as e:
        print("Error in cost calculation and logging: ", e)
        return "Failed!"

def get_tokens_and_cost(text: str, std_prompt: str, model_name: str, flag: str = 'query'):
    """
    Takes an input query and returns the cost.
    1. Cost of encoding query + prompt
    2. Cost of answer generation by the model
    """
    #print("in get_tokens_and_cost")
    # initialize tokenizer
    tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")
    if model_name.startswith('gpt-4'):
        if "32k" in model_name:
            # 32k context
            prompt_cost_per_token: float = 0.06/1000
            completion_cost_per_token: float = 0.12/1000
        else:
            # 8k context
            prompt_cost_per_token: float = 0.03/1000
            completion_cost_per_token: float = 0.06/1000

    elif model_name.startswith('gpt-3.5-turbo'):
        if "16k" in model_name:
            # 16k context
            prompt_cost_per_token: float = 0.003/1000
            completion_cost_per_token: float = 0.004/1000
        else:
            # 4k context
            prompt_cost_per_token: float = 0.0015/1000
            completion_cost_per_token: float = 0.002/1000

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


def get_course_cost(course_name: str, days=0):
    """
    Returns a dataframe of conversations for the last given days and course.
    If days=0, return all conversations for the course.
    """
    # initialize supabase
    supabase_client = supabase.create_client(supabase_url=os.getenv('SUPABASE_URL'), 
                                             supabase_key=os.getenv('SUPABASE_API_KEY'))
    try:
        if days > 0:
            # fetch conversations for the last given days
            current_date = datetime.now()
            days_ago = current_date - timedelta(days=days)
            given_date = days_ago.strftime("%Y-%m-%d")
            print("Current Date:", current_date.strftime("%Y-%m-%d"))
            print("30 Days Ago:", given_date)
            response = supabase_client.table("llm-convo-monitor").select("id", count='exact').eq("course_name", course_name).gte('created_at', given_date).order('id', desc=False).execute()
            
        else:
            # fetch all conversations for the course
            response = supabase_client.table("llm-convo-monitor").select("id", count='exact').eq("course_name", course_name).order('id', desc=False).execute()
        
        total_count = response.count
        id_data = response.data
        # get the first conversation ID
        min_id = id_data[0]['id']
        current_items = []
        #print("Total count: ", total_count)
        #print("First ID: ", min_id)

        # get conversations in batches of 25
        while len(current_items) < total_count:
            try:
                if len(current_items) == 0: # first iteration
                    response = supabase_client.table("llm-convo-monitor").select("id, convo", count='exact').eq("course_name", course_name).gte('id', min_id).order('id', desc=False).limit(25).execute()
                else:
                    response = supabase_client.table("llm-convo-monitor").select("id, convo", count='exact').eq("course_name", course_name).gt('id', min_id).order('id', desc=False).limit(25).execute()
                current_items += response.data
                min_id = response.data[-1]['id']
                #print("Length of current items: ", len(current_items))
            except Exception as e:
                print("Error in fetching conversations: ", e)
                break

        # all data is in current_items here
        print("Final length of current items: ", len(current_items))
        convo_df = pd.DataFrame(current_items)
        convo_df = convo_df['convo']

        total_queries = 0
        list_of_prompt_costs = []
        list_of_prompt_token_lengths = []
        list_of_response_costs = []
        list_of_response_token_lengths = []

        for row in convo_df:
        
            messages = row['messages']
            model_id = row['model']['id']
            prompt = row['prompt']

            for message in messages:
                content = message['content']
                
                if message['role'] == 'user':
                    # calculate prompt costs
                    # adding context only to input (user) messages
                    if 'contexts' in message:
                        contexts = message['contexts']
                        for context in contexts:
                            if 'text' in context: # some contexts don't have text
                                content = content + " " + context['text']

                    total_queries += 1
                    query_cost, query_tokens = get_tokens_and_cost(content, prompt, model_id, flag='query')
                    list_of_prompt_costs.append(query_cost)
                    list_of_prompt_token_lengths.append(query_tokens)
                else:
                    # calculate response costs
                    response_cost, response_tokens = get_tokens_and_cost(content, prompt, model_id, flag='response')
                    list_of_response_costs.append(response_cost)
                    list_of_response_token_lengths.append(response_tokens)
        # print("all costs collected")
        # at this point, we have tokens and costs for all conversations
        total_prompt_cost = round(sum(list_of_prompt_costs), 4)
        total_response_cost = round(sum(list_of_response_costs), 4)
        total_course_cost = round(sum(list_of_prompt_costs) + sum(list_of_response_costs), 4)
        total_embeddings_cost = 0.0
        total_tokens = sum(list_of_prompt_token_lengths) + sum(list_of_response_token_lengths)
        # print("total prompt cost: ", total_prompt_cost)
        # print("total response cost: ", total_response_cost)
        # print("total course cost: ", total_course_cost)
        # print("total queries: ", total_queries)
        # print("total prompt tokens: ", sum(list_of_prompt_token_lengths))
        # print("total response tokens: ", sum(list_of_response_token_lengths))
        # print("total tokens: ", total_tokens)
        # print("-------------------------------------")

        cost_dict = {"total_tokens": total_tokens, 
                     "total_prompt_price": total_prompt_cost,
                     "total_completions_price": total_response_cost,
                     "total_embeddings_price": total_embeddings_cost,
                     "total_queries": total_queries,
                     "course_name": course_name}

        return cost_dict
    
    except Exception as e:
        print("Error in fetching conversations: ", e)
        return "Failed!"
    




def course_price_logging(course_name: str, conversation):   
    """
    Calculates prices for current conversation object and adds them to the course table.
    1. Check if course exists in the table.
    2. If yes, update the entry with current convo cost.
    3. If no, call get_complete_cost_of_course and add the entry to the table.
    """
    # initialize supabase
    supabase_client = supabase.create_client(supabase_url=os.getenv('SUPABASE_URL'), 
                                             supabase_key=os.getenv('SUPABASE_API_KEY'))
    
    try:
        # calculate cost of current conversation object

        # check if entry exists in the table
        response = supabase_client.table("uiuc-course-table").select("*").eq("course_name", course_name).execute()
        if len(response.data) == 0:
            # add new entry
            print("Price tracking entry does not exist. Creating a new entry...")
            full_cost = get_complete_cost_of_course(course_name)

        # add the current conversation costs to the table

            
    except Exception as e:
        print("Error in cost calculation and logging: ", e)
        return "Failed!"