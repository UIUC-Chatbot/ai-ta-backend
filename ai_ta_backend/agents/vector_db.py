import inspect
import os
import traceback

import langchain
from dotenv import load_dotenv
from langchain.agents import AgentType, Tool, initialize_agent
from langchain.agents.react.base import DocstoreExplorer
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings, ChatOpenAI, OpenAIEmbeddings
from langchain.docstore.base import Docstore
from langchain_community.tools import VectorStoreQATool
from langchain_community.vectorstores import Qdrant
from qdrant_client import QdrantClient

load_dotenv(override=True)

langchain.debug = False
VERBOSE = True


def get_vectorstore_retriever_tool(course_name: str,
                                   name: str,
                                   description: str,
                                   openai_model_name='gpt-3.5-turbo-16k',
                                   temperature=0.1,
                                   top_k=8) -> VectorStoreQATool:
  r"""
    course name str: Name of course on uiuc-chat as appears in URL-bar; yes it's case sensitive.

    Usage: 
    ```
      QAtool = get_vectorstore_retriever_tool(course_name='langchain-docs')
      print(QAtool._run("query"))
      print("FINAL RESULT\n", get_vectorstore_retriever_tool(search_query="How do Plan and Execute agents work in Langchain?", course_name='langchain-docs'))
    ```
    
    langchain_docs_tool._run(search_query)
  """
  try:
    qdrant_client = QdrantClient(
        url=os.getenv('QDRANT_URL'),
        api_key=os.getenv('QDRANT_API_KEY'),
    )

    langchain_docs_vectorstore = Qdrant(
        client=qdrant_client,
        collection_name=os.getenv('QDRANT_COLLECTION_NAME'),  # type: ignore
        embeddings=AzureOpenAIEmbeddings() if os.environ['OPENAI_API_TYPE'] == 'azure' else OpenAIEmbeddings())

    if os.environ['OPENAI_API_TYPE'] == 'azure':
      llm = AzureChatOpenAI(
          temperature=0,
          model="gpt-4-0613",
          max_retries=3,
          request_timeout=60 * 3,
          deployment_name=os.environ['AZURE_OPENAI_ENGINE']
      )
    else:
      llm: ChatOpenAI = ChatOpenAI(
          temperature=0,
          model="gpt-4-0613",
          max_retries=500,
          # request_timeout=60 * 3,
          streaming=True)

    return VectorStoreQATool(
        vectorstore=langchain_docs_vectorstore,
        llm=llm,  # type: ignore
        name=name,
        description=description,
        retriever_kwargs={'filter': {
            'course_name': course_name,
            'k': top_k
        }})
  except Exception as e:
    # return full traceback to front end
    print(
        f"In /getTopContexts. Course: {course_name} \nTraceback: {traceback.extract_tb(e.__traceback__)}❌❌ Error in {inspect.currentframe().f_code.co_name}:\n{e}"
    )  # type: ignore
    raise e


def get_docstore_agent(docstore: Docstore):
  """This returns an agent. Usage of this agent: react.run(question)
  e.g.
  ```
    question = "Author David Chanoff has collaborated with a U.S. Navy admiral who served as the ambassador to the United Kingdom under which President?"
    react.run(question)
  ```
  """
  if docstore is None:
    doc_explorer = DocstoreExplorer(langchain.Wikipedia())
  else:
    doc_explorer = DocstoreExplorer(docstore)

  tools = [
      Tool(
          name="Search",
          func=doc_explorer.search,
          description="useful for when you need to ask with search",
      ),
      Tool(
          name="Lookup",
          func=doc_explorer.lookup,
          description="useful for when you need to ask with lookup",
      ),
  ]

  if os.environ['OPENAI_API_TYPE'] == 'azure':
    llm = AzureChatOpenAI(temperature=0,
                          model="gpt-4-0613",
                          max_retries=3,
                          request_timeout=60 * 3,
                          deployment_name=os.environ['AZURE_OPENAI_ENGINE'])  # type: ignore
  else:
    llm = ChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=3, request_timeout=60 * 3)  # type: ignore
  react = initialize_agent(tools, llm, agent=AgentType.REACT_DOCSTORE, verbose=VERBOSE)
  return react
