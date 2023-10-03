import supabase
import pandas as pd
import os
from typing import List


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

    for row in convo_df:
        messages = row['messages']
        for message in messages:
            if message['role'] == 'user' and message['content'] != '':
                total_queries += 1

    print("Total queries: ", total_queries)

    return [total_queries]