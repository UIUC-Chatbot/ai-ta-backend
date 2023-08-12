import asyncio
import os

import langchain
from dotenv import load_dotenv
from langchain.agents import AgentType, Tool, initialize_agent, load_tools
from langchain.agents.agent_toolkits import PlayWrightBrowserToolkit
from langchain.agents.react.base import DocstoreExplorer
from langchain.callbacks import HumanApprovalCallbackHandler
from langchain.chat_models import ChatOpenAI
from langchain.docstore.base import Docstore
from langchain.memory import ConversationBufferMemory
from langchain.prompts import MessagesPlaceholder
from langchain.tools import ShellTool
from langchain.tools.base import BaseTool
from langchain.tools.playwright.utils import \
    create_sync_playwright_browser  # A synchronous browser is available, though it isn't compatible with jupyter.
from langchain.tools.playwright.utils import create_async_playwright_browser

os.environ["LANGCHAIN_TRACING"] = "true"  # If you want to trace the execution of the program, set to "true"
langchain.debug = True
VERBOSE = True


def get_docstore_agent(docstore: Docstore | None = None):
  """This returns an agent. Usage of this agent: react.run(question)"""
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

  llm = ChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=3, request_timeout=60 * 3)  # type: ignore
  react = initialize_agent(tools, llm, agent=AgentType.REACT_DOCSTORE, verbose=VERBOSE)
  return react
