import inspect
import json
import os
import time
import traceback
from typing import Any, Dict, List, Union

import supabase
import tiktoken
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.tools import VectorStoreQATool
from langchain.vectorstores import Qdrant
from qdrant_client import QdrantClient, models
from sqlalchemy import over

load_dotenv(override=True)


def get_vectorstore_retriever_tool(course_name: str, name: str, description: str, openai_model_name='gpt-3.5-turbo-16k', temperature=0.1, top_k=8) -> VectorStoreQATool:
  """
    course name str: 

    Usage: 
    ```
      QAtool = get_vectorstore_retriever_tool(course_name='langchain-docs')
      print(QAtool._run("query"))
      print("FINAL RESULT\n", get_vectorstore_retriever_tool(search_query="How do Plan and Execute agents work in Langchain?", course_name='langchain-docs'))
    ```
    
    langchain_docs_tool._run(search_query)
  """
  print(f"in get_vectorstore_retriever_tool() for course {course_name}")

  try:
    qdrant_client = QdrantClient(
        url=os.getenv('QDRANT_URL'),
        api_key=os.getenv('QDRANT_API_KEY'),
    )

    langchain_docs_vectorstore = Qdrant(
        client=qdrant_client,
        collection_name=os.getenv('QDRANT_COLLECTION_NAME'),  # type: ignore
        embeddings=OpenAIEmbeddings()
    )
    
    return VectorStoreQATool(
      vectorstore=langchain_docs_vectorstore, 
      llm=ChatOpenAI(model_name=openai_model_name, temperature=temperature),  # type: ignore
      name=name,
      description=description,
      retriever_kwargs={'filter': {'course_name': course_name, 'k': top_k}}
    )
  except Exception as e:
    # return full traceback to front end
    print(f"In /getTopContexts. Course: {course_name} ||| search_query: {search_query}\nTraceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:\n{e}") # type: ignore
    raise e

## if name is main
if __name__ == "__main__":
  # What are a few of the types of Agents in Langchain?
  # How do I format a prompt template in Langchain? Any examples?
  # search_query="How do Plan and Execute agents work in Langchain?",
  print("FINAL RESULT\n", get_vectorstore_retriever_tool(course_name='langchain-docs', name='hi', description='hi'))
