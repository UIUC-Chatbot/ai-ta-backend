# Env for kastan: 

import inspect
import json
import os
import time
import traceback

import openai
import ray
import replicate
import requests
from dotenv import load_dotenv
from langchain import hub
from langchain.prompts import PromptTemplate
#from openai import OpenAI

from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import partial
from multiprocessing import Pool, Manager

from ai_ta_backend.utils_tokenization import count_tokens_and_cost

load_dotenv(override=True)
LANGSMITH_PROMPT_OBJ = hub.pull("kastanday/filter-unrelated-contexts-zephyr")

## Local LLMs  USAGE DOCS: https://kastanday.notion.site/LLM-Serving-on-prem-OpenAI-Clone-bb06028266d842b0872465f552684177 ## 

def list_context_filtering(contexts, user_query, max_time_before_return=45, max_concurrency=100):
  """
  Main function for filtering contexts. Use this when dealing with a List[Dicts]. To be called after context_padding 
  in getTopContextsWithMQR(). It is also used with batch_context_filtering.
  This function multi-processes a list of contexts.

  Args: contexts (list of dicts), user_query (str), max_time_before_return (int), max_concurrency (int)
  Returns: filtered_contexts (list of dicts)
  """
  
  start_time = time.monotonic()
  
  # call filter contexts function
  with Manager() as manager:
    filtered_contexts = manager.list()
    partial_func1 = partial(anyscale_completion, user_query=user_query, langsmith_prompt_obj=LANGSMITH_PROMPT_OBJ)
    partial_func2 = partial(select_context, result=filtered_contexts)

    with ProcessPoolExecutor(max_workers=30) as executor:
      anyscale_responses = list(executor.map(partial_func1, contexts))
      if len(anyscale_responses) > 0:
        executor.map(partial_func2, anyscale_responses)
      else:
        print("LLM responses are empty.")
      executor.shutdown()
 
    filtered_contexts = list(filtered_contexts)
  print(f"⏰ Context filtering runtime: {(time.monotonic() - start_time):.2f} seconds")

  print("len of filtered contexts: ", len(filtered_contexts))
  return filtered_contexts

def batch_context_filtering(batch_docs, user_query, max_time_before_return=45, max_concurrency=100):
  """
  Main function for filtering contexts. Use this when dealing with List[List[Docs]]. To be called between 
  batch_vector_search() and reciprocal_ranking().
  This function multi-processes a list of list of contexts.

  Args: batch_docs (list of list of docs), user_query (str), max_time_before_return (int), max_concurrency (int)
  Returns: filtered_contexts (list of list of docs)
  """
  
  start_time = time.monotonic()

  partial_func = partial(list_context_filtering, user_query=user_query, max_time_before_return=max_time_before_return, max_concurrency=max_concurrency)
  with ProcessPoolExecutor(max_workers=5) as executor:
    processed_docs = list(executor.map(partial_func, batch_docs))
    
  processed_docs = list(processed_docs)
  print(f"⏰ Context filtering runtime: {(time.monotonic() - start_time):.2f} seconds")

  return processed_docs


def anyscale_completion(context, user_query, langsmith_prompt_obj):
  """
  Runs the Anyscale completion API call.
  Args: context (dict), user_query (str), langsmith_prompt_obj (PromptTemplate)
  Returns: completion_object (dict)
  """
  api_start_time = time.monotonic()
  # use first final_prompt when using batch_context_filtering as start point and second when using list_context_filtering as start point
  final_prompt = str(langsmith_prompt_obj.format(context=context.page_content, user_query=user_query))
  #final_prompt = str(langsmith_prompt_obj.format(context=context['text'], user_query=user_query))
  try: 
    ret = openai.ChatCompletion.create(
          api_base = "https://api.endpoints.anyscale.com/v1",
          api_key=os.environ["ANYSCALE_ENDPOINT_TOKEN"],
          model = "HuggingFaceH4/zephyr-7b-beta",
          messages=[{"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": final_prompt}],
          temperature=0.3, 
          max_tokens=250,
      )
    completion = ret["choices"][0]["message"]["content"]

    print(f"⏰ Anyscale runtime: {(time.monotonic() - api_start_time):.2f} seconds")
    return {"completion": completion, "context": context}
  except Exception as e: 
    print(f"Error: {e}")

def select_context(completion_object, result):
  """
  Uses parse_result() to determine if the context should be passed to the frontend.
  Args: completion_object (dict), result (list of dicts)
  Returns: None
  """
  if parse_result(completion_object['completion']):
    result.append(completion_object['context'])
  
def parse_result(result):
  """
  Parses the result of the LLM completion API call.
  Args: result (str) -- the completion part of Anyscale response
  """
  lines = result.split('\n')
  for line in lines:
    if 'Final answer' in line:
      return 'yes' in line.lower()
  return False 
 

#----------------------- RAY CODE BELOW ----------------------------------------------------------------------------#

# @ray.remote
# class AsyncActor:
#   def __init__(self):
#     pass

#   def filter_context(self, context, user_query, langsmith_prompt_obj):
#     final_prompt = str(langsmith_prompt_obj.format(context=context['text'], user_query=user_query))
#     #print(f"-------\nfinal_prompt:\n{final_prompt}\n^^^^^^^^^^^^^")
#     try: 
#       # completion = run_model(final_prompt)
#       #completion = run_replicate(final_prompt)
#       completion = run_anyscale(final_prompt)
      
#       return {"completion": completion, "context": context}
#     except Exception as e: 
#       print(f"Error: {e}")

# def run_model(prompt, max_tokens=300, temp=0.3, **kwargs):
#   '''
#   Local LLMs  USAGE DOCS: https://kastanday.notion.site/LLM-Serving-on-prem-OpenAI-Clone-bb06028266d842b0872465f552684177 ## 
#   '''

#   url = "http://api.kastan.ai/v1/completions?model=HuggingFaceH4/zephyr-7b-alpha"
#   headers = {
#       'Content-Type': 'application/json'
#   }
#   data = {
#       "prompt": prompt,
#       "max_tokens": max_tokens,
#       "temperature": temp,
#       **kwargs
#   }

#   try: 
#     response = requests.post(url, headers=headers, data=json.dumps(data))
#     return response.json()['choices'][0]['text']
#   except Exception as e:
#     # Probably cuda OOM error. 
#     raise ValueError(f"🚫🚫🚫 Failed inference attempt. Response: {response.json()}\nError: {e}\nPromt that caused error: {prompt}")

# def run_replicate(prompt):
#   output = replicate.run(
#     "tomasmcm/zephyr-7b-beta:961cd6665b811d0c43c0b9488b6dfa85ff5c7bfb875e93b4533e4c7f96c7c526",
#     input={
#       "top_k": 50,
#       "top_p": 0.95,
#       "prompt": prompt,
#       "temperature": 0.3,
#       "max_new_tokens": 250,
#       "presence_penalty": 1
#     }
#   )
#   print(output)
#   return output

# def run_anyscale(prompt):
#   api_start_time = time.monotonic()
#   ret = openai.ChatCompletion.create(
#           api_base = "https://api.endpoints.anyscale.com/v1",
#           api_key=os.environ["ANYSCALE_ENDPOINT_TOKEN"],
#           # model="meta-llama/Llama-2-70b-chat-hf",
#           #model="mistralai/Mistral-7B-Instruct-v0.1",
#           model = "HuggingFaceH4/zephyr-7b-beta",
#           messages=[{"role": "system", "content": "You are a helpful assistant."},
#                     {"role": "user", "content": prompt}],
#           temperature=0.3, 
#           max_tokens=250,
#       )
#   print(f"⏰ Anyscale runtime: {(time.monotonic() - api_start_time):.2f} seconds")
#   return ret["choices"][0]["message"]["content"]


# def parse_result(result):
#   lines = result.split('\n')
#   for line in lines:
#     if 'Final answer' in line:
#       return 'yes' in line.lower()
#   return False

# def ray_context_filtering(contexts, user_query, max_tokens_to_return=3000, max_time_before_return=None, max_concurrency=100):
#   
#  # Main function for filtering contexts using RAY. Use this when dealing with a list of contexts.
# 
# 
#   langsmith_prompt_obj = hub.pull("kastanday/filter-unrelated-contexts-zephyr")
  
#   print("Num jobs to run:", len(contexts))

#   actor = AsyncActor.options(max_concurrency=max_concurrency).remote()
#   result_futures = [actor.filter_context.remote(c, user_query, langsmith_prompt_obj) for c in contexts]
#   print("Num futures:", len(result_futures))
#   #print("Result futures:", result_futures)
  
#   start_time = time.time()
#   for i in range(0, len(result_futures)): 
#     try: 
#       ready, not_ready = ray.wait(result_futures)
#       result = ray.get(ready[0])
      
#       if result is None:
#         print("RESULT WAS NONE, llm inference probably failed")
#         continue
      
#       if parse_result(result['completion']): 
#         yield result['context']
      
#       elapsed_time = (time.time() - start_time)
#       avg_task_time = elapsed_time / (i+1)
#       estimated_total_runtime = avg_task_time * len(contexts)
      
#       print(f"📌 Completed {i+1} of {len(contexts)}")
#       print(f"⏰ Running total of elapsed time: {elapsed_time:.2f} seconds\n🔮 Estimated total runtime: {estimated_total_runtime:.2f} seconds.\n")
#       print(f"⏰👻 avg_task_time (s): {avg_task_time:.2f}")
#       # print(f"📜 Passage: {result['context']['text']}")
#       # print(f"✅ Result: {result['completion']}")
      
#       if max_time_before_return is not None and elapsed_time >= max_time_before_return:
#         break
      
#     except Exception as e:
#       print("-----------❌❌❌❌------------START OF ERROR-----------❌❌❌❌------------")
#       print(f"Error in {inspect.currentframe().f_code.co_name}: {e}") # print function name in error.
#       print(f"Traceback:")
#       print(traceback.print_exc())
#     finally: 
#       result_futures = not_ready
#       if not result_futures:
#         break


 

# # ! CONDA ENV: llm-serving
# if __name__ == "__main__":
#   #ray.init() 
#   start_time = time.monotonic()
#   # print(len(CONTEXTS))

#   final_passage_list = list(ray_context_filtering(contexts=CONTEXTS*2, user_query=USER_QUERY, max_time_before_return=45, max_concurrency=20))

#   print("✅✅✅ FINAL RESULTS: \n" + '\n'.join(json.dumps(r, indent=2) for r in final_passage_list))
#   print("✅✅✅ TOTAL RETURNED: ", len(final_passage_list))
#   print(f"⏰⏰⏰ Runtime: {(time.monotonic() - start_time):.2f} seconds")