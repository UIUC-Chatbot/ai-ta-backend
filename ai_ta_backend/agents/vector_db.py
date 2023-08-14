import inspect
import json
import os
import time
import traceback
from typing import Any, Dict, List, Union

import supabase
import tiktoken
from dotenv import load_dotenv
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Qdrant
from qdrant_client import QdrantClient, models

load_dotenv()


def get_top_contexts_uiuc_chatbot(search_query: str, course_name: str, token_limit: int = 4_000) -> Union[List[Dict], str]:
  """Here's a summary of the work.

  /GET arguments
    course name (optional) str: A json response with TBD fields.
    
  Returns
    JSON: A json response with TBD fields. See main.py:getTopContexts docs.
    or 
    String: An error message with traceback.
  """
  print("in get_top_contexts_uiuc_chatbot()")

  try:
    qdrant_client = QdrantClient(
        url=os.getenv('QDRANT_UIUC_CHATBOT_URL'),
        api_key=os.getenv('QDRANT_UIUC_CHATBOT_API_KEY'),
    )

    vectorstore = Qdrant(
        client=qdrant_client,
        collection_name=os.getenv('QDRANT_UIUC_CHATBOT_COLLECTION_NAME'),  # type: ignore
        embeddings=OpenAIEmbeddings())  # type: ignore

    # TODO: change back to 50+ once we have bigger qdrant DB.
    top_n = 80  # HARD CODE TO ENSURE WE HIT THE MAX TOKENS
    start_time_overall = time.monotonic()
    found_docs = vectorstore.similarity_search(search_query, k=top_n, filter={'course_name': course_name})
    if len(found_docs) == 0:
      return []

    pre_prompt = "Please answer the following question. Use the context below, called your documents, only if it's helpful and don't use parts that are very irrelevant. It's good to quote from your documents directly, when you do always use Markdown footnotes for citations. Use react-markdown superscript to number the sources at the end of sentences (1, 2, 3...) and use react-markdown Footnotes to list the full document names for each number. Use ReactMarkdown aka 'react-markdown' formatting for super script citations, use semi-formal style. Feel free to say you don't know. \nHere's a few passages of the high quality documents:\n"

    # count tokens at start and end, then also count each context.
    input_str = pre_prompt + '\n\nNow please respond to my query: ' + search_query
    token_counter, _ = count_tokens_and_cost(prompt=input_str)
    valid_docs = []
    for d in found_docs:
      doc_string = f"Document: {d.metadata['readable_filename']}{', page: ' + str(d.metadata['pagenumber_or_timestamp']) if d.metadata['pagenumber_or_timestamp'] else ''}\n{d.page_content}\n"
      num_tokens, prompt_cost = count_tokens_and_cost(prompt=doc_string)
      # print(f"token_counter: {token_counter}, num_tokens: {num_tokens}, max_tokens: {token_limit}")
      if token_counter + num_tokens <= token_limit:
        token_counter += num_tokens
        valid_docs.append(d)
      else:
        break

    print(f"Total tokens: {token_counter} total docs: {len(found_docs)} num docs used: {len(valid_docs)}")
    print(f"Course: {course_name} ||| search_query: {search_query}")
    print(f"⏰ ^^ Runtime of getTopContexts: {(time.monotonic() - start_time_overall):.2f} seconds")

    return valid_docs
  except Exception as e:
    # return full traceback to front end
    err: str = f"In /getTopContexts. Course: {course_name} ||| search_query: {search_query}\nTraceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:\n{e}"  # type: ignore
    print(err)
    return err


def count_tokens_and_cost(prompt: str,
                          completion: str = '',
                          openai_model_name: str = "gpt-3.5-turbo"):  # -> tuple[int, float] | tuple[int, float, int, float]:
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
  encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")  # I think they all use the same encoding
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


## if name is main
if __name__ == "__main__":
  print(get_top_contexts_uiuc_chatbot(search_query="what's that", course_name='langchain'))
