import json
import os
import time
# from dotenv import load_dotenv

import openai
import ray
import requests
from langchain import hub
from posthog import Posthog

# import replicate
# from transformers import AutoTokenizer

# load_dotenv(override=True)
# tokenizer = AutoTokenizer.from_pretrained("HuggingFaceH4/zephyr-7b-beta")


@ray.remote
class AsyncActor:

  def filter_context(self, context, user_query, langsmith_prompt_obj):
    final_prompt = str(langsmith_prompt_obj.format(context=context, user_query=user_query))
    # print(f"-------\nfinal_prompt:\n{final_prompt}\n^^^^^^^^^^^^^")
    try:
      # completion = run_caii_hosted_llm(final_prompt)
      # completion = run_replicate(final_prompt)
      completion = run_anyscale(final_prompt)
      return {"completion": completion, "context": context}
    except Exception as e:
      print(f"Error: {e}")


def run_caii_hosted_llm(prompt, max_tokens=300, temp=0.3, **kwargs):
  """
  Local LLMs  USAGE DOCS: https://kastanday.notion.site/LLM-Serving-on-prem-OpenAI-Clone-bb06028266d842b0872465f552684177 ## 
  """

  url = "http://api.kastan.ai/v1/completions?model=HuggingFaceH4/zephyr-7b-alpha"
  headers = {'Content-Type': 'application/json'}
  data = {"prompt": prompt, "max_tokens": max_tokens, "temperature": temp, **kwargs}

  try:
    response = requests.post(url, headers=headers, data=json.dumps(data), timeout=180)
    return response.json()['choices'][0]['text']
  except Exception as e:
    # Probably cuda OOM error.
    raise ValueError(
        f"🚫🚫🚫 Failed inference attempt. Response: {response.json()}\nError: {e}\nPromt that caused error: {prompt}"
    ) from e


def run_replicate(prompt):
  output = None
  # output = replicate.run("tomasmcm/zephyr-7b-beta:961cd6665b811d0c43c0b9488b6dfa85ff5c7bfb875e93b4533e4c7f96c7c526",
  #                        input={
  #                            "top_k": 50,
  #                            "top_p": 0.95,
  #                            "prompt": prompt,
  #                            "temperature": 0.3,
  #                            "max_new_tokens": 250,
  #                            "presence_penalty": 1
  #                        })
  print(output)
  return output


def run_anyscale(prompt, model_name="HuggingFaceH4/zephyr-7b-beta"):
  start_time = time.monotonic()
  ret = openai.ChatCompletion.create(
      api_base="https://api.endpoints.anyscale.com/v1",
      api_key=os.environ["ANYSCALE_ENDPOINT_TOKEN"],
      api_type="openai",
      # model="mistralai/Mistral-7B-Instruct-v0.1",
      model="HuggingFaceH4/zephyr-7b-beta",
      messages=[{
          "role": "system",
          "content": "You are a helpful assistant."
      }, {
          "role": "user",
          "content": prompt
      }],
      temperature=0.3,
      max_tokens=250,
  )

  output = ret["choices"][0]["message"]["content"]
  print("Response from Anyscale:", output[:150])

  # input_length = len(tokenizer.encode(prompt))
  # output_length = len(tokenizer.encode(output))
  # Input tokens {input_length}, output tokens: {output_length}"
  print(f"^^^^ one anyscale call Runtime: {(time.monotonic() - start_time):.2f} seconds.")
  return output


def parse_result(result: str):
  lines = result.split('\n')
  for line in lines:
    if 'Final answer' in line:
      return 'yes' in line.lower()
  return False


def filter_top_contexts(contexts, user_query: str, timeout: float = None, max_concurrency: int = 180):

  print("⏰⏰⏰ Starting filter_top_contexts() ⏰⏰⏰")
  # print(len(contexts))
  # print(contexts)
  # raise ValueError("STOPPING HERE")

  timeout = timeout or float(os.environ["FILTER_TOP_CONTEXTS_TIMEOUT_SECONDS"])
  langsmith_prompt_obj = hub.pull("kastanday/filter-unrelated-contexts-zephyr")
  posthog = Posthog(project_api_key=os.environ['POSTHOG_API_KEY'], host='https://app.posthog.com')

  print("Max concurrency:", max_concurrency)
  print("Num contexts to filter:", len(contexts))

  # START TASKS
  actor = AsyncActor.options(max_concurrency=max_concurrency, num_cpus=0.001).remote()
  result_futures = [actor.filter_context.remote(c, user_query, langsmith_prompt_obj) for c in contexts]

  start_time = time.time()
  done_tasks, in_progress = ray.wait(result_futures,
                                     num_returns=len(result_futures),
                                     timeout=timeout,
                                     fetch_local=False)
  for task in in_progress:
    ray.cancel(task)
  results = ray.get(done_tasks)

  best_contexts_to_keep = [
      r['context'] for r in results if r and 'context' in r and 'completion' in r and parse_result(r['completion'])
  ]

  posthog.capture('distinct_id_of_the_user',
                  event='filter_top_contexts',
                  properties={
                      'user_query': user_query,
                      'course_name': contexts[0].metadata.get('course_name', None),
                      'percent_kept': len(best_contexts_to_keep) / len(results),
                      'total_docs_processed': len(results),
                      'total_docs_kept': len(best_contexts_to_keep)
                  })

  print("🧠🧠 TOTAL DOCS PROCESSED BY ANYSCALE FILTERING:", len(results))
  print("🧠🧠 TOTAL DOCS KEPT, AFTER FILTERING:", len(best_contexts_to_keep))
  print(f"⏰ Total elapsed time: {(time.time() - start_time):.2f} seconds")

  return best_contexts_to_keep


def run_main():
  start_time = time.monotonic()
  # final_passage_list = filter_top_contexts(contexts=CONTEXTS * 2, user_query=USER_QUERY)
  # print("✅✅✅ TOTAL included in results: ", len(final_passage_list))
  print(f"⏰⏰⏰ Runtime: {(time.monotonic() - start_time):.2f} seconds")
  # print("Total contexts:", len(CONTEXTS) * 2)


# ! CONDA ENV: llm-serving
if __name__ == "__main__":
  run_main()
