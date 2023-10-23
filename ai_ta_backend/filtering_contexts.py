import json

import requests
from langchain.prompts import PromptTemplate


def filter_contexts(contexts):
  prompt_template = PromptTemplate.from_template(
      "<|system|>"
      "{system_prompt}"
      "<|user|>"
      "{user_prompt}"
      "<|assistant|>"
  )

  final_prompt = prompt_template.format(
      system_prompt="You are concise, and only give the user exactly what they asking for. Follow instructions precisely and do not say anything extra.",
      # user_prompt="How many helicopters can a human eat in one sitting?",
      user_prompt="Say 'False' and nothing else. Do not include any filler language, reply with just 'False' Go:",
  )

  ## Local LLMs  USAGE DOCS: https://kastanday.notion.site/LLM-Serving-on-prem-OpenAI-Clone-bb06028266d842b0872465f552684177 ## 

  url = "http://api.kastan.ai/v1/completions?model=HuggingFaceH4/zephyr-7b-alpha"
  headers = {
      'Content-Type': 'application/json'
  }
  data = {
      "prompt": final_prompt,
      "max_tokens": 10,
      "temperature": .3,
  }
  response = requests.post(url, headers=headers, data=json.dumps(data))
  print(response.json()['choices'][0]['text'])

  return response.json()['choices'][0]['text']