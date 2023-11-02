import asyncio
import os
from typing import List

import langchain
from dotenv import load_dotenv
from langchain import SerpAPIWrapper
from langchain.agents import AgentType, Tool, initialize_agent, load_tools
from langchain.agents.agent_toolkits import PlayWrightBrowserToolkit
from langchain.agents.agent_toolkits.github.toolkit import GitHubToolkit
from langchain.agents.react.base import DocstoreExplorer
from langchain.callbacks import HumanApprovalCallbackHandler
from langchain.chains import ConversationalRetrievalChain
from langchain.chat_models import ChatOpenAI
from langchain.docstore.base import Docstore
from langchain.llms import OpenAI, OpenAIChat
from langchain.memory import ConversationBufferMemory
from langchain.prompts import MessagesPlaceholder
from langchain.retrievers import ArxivRetriever
from langchain.tools import (ArxivQueryRun, PubmedQueryRun, VectorStoreQATool, VectorStoreQAWithSourcesTool,
                             WikipediaQueryRun, WolframAlphaQueryRun)
from langchain.tools.base import BaseTool
from langchain.tools.playwright.utils import create_sync_playwright_browser, create_async_playwright_browser
from langchain.utilities.github import GitHubAPIWrapper
from langchain.vectorstores import Qdrant
from qdrant_client import QdrantClient
from autogen.code_utils import execute_code

from ai_ta_backend.agents.vector_db import get_vectorstore_retriever_tool
from ai_ta_backend.vector_database import Ingest

load_dotenv(override=True, dotenv_path='../.env')

os.environ["LANGCHAIN_TRACING"] = "true"  # If you want to trace the execution of the program, set to "true"
langchain.debug = False
VERBOSE = True

def get_tools(llm, sync=True):
  '''Main function to assemble tools for ML for Bio project.'''
  # WEB BROWSER
  browser_toolkit = None
  if sync:
    sync_browser = create_sync_playwright_browser()
    browser_toolkit = PlayWrightBrowserToolkit.from_browser(sync_browser=sync_browser)
  else:
    # TODO async is work in progress... not functional yet.
    async_browser = create_async_playwright_browser()
    browser_toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=async_browser)
  browser_tools = browser_toolkit.get_tools()

  # HUMAN
  human_tools = load_tools(["human"], llm=llm, input_func=get_human_input)
  # GOOGLE SEARCH
  search = load_tools(["serpapi"])

  # GITHUB
  github = GitHubAPIWrapper()  # type: ignore
  toolkit = GitHubToolkit.from_github_api_wrapper(github)
  github_tools: list[BaseTool] = toolkit.get_tools()

  # ARXIV SEARCH
  arxiv_tool = ArxivQueryRun()

  #TODO:WikipediaQueryRun, WolframAlphaQueryRun, PubmedQueryRun, ArxivQueryRun

  # TODO: more vector stores per Bio package: trimmomatic, gffread, samtools, salmon, DESeq2 and ggpubr
  docs_tools: List[VectorStoreQATool] = [
    get_vectorstore_retriever_tool(course_name='langchain-docs', name='Langchain docs', description="Build context-aware, reasoning applications with LangChain's flexible abstractions and AI-first toolkit."),
    get_vectorstore_retriever_tool(course_name='ml4bio-star', name='STAR docs', description='Basic STAR workflow consists of 2 steps: (1) Generating genome indexes files and (2) Mapping reads to the genome'),
    get_vectorstore_retriever_tool(course_name='ml4bio-fastqc', name='FastQC docs', description='FastQC aims to provide a simple way to do some quality control checks on raw sequence data coming from high throughput sequencing pipelines. It provides a modular set of analyses which you can use to give a quick impression of whether your data has any problems of which you should be aware before doing any further analysis. It works with data from BAM, SAM or FastQ files'),
    get_vectorstore_retriever_tool(course_name='ml4bio-multiqc', name='MultiQC docs', description="MultiQC is a reporting tool that parses results and statistics from bioinformatics tool outputs, such as log files and console outputs. It helps to summarize experiments containing multiple samples and multiple analysis steps. It's designed to be placed at the end of pipelines or to be run manually when you've finished running your tools."),
    get_vectorstore_retriever_tool(course_name='ml4bio-bioconductor', name='Bioconductor docs', description="Bioconductor is a project that contains hundreds of individual R packages. They're all high quality libraries that provide widespread access to a broad range of powerful statistical and graphical methods for the analysis of genomic data. Some of them also facilitate the inclusion of biological metadata in the analysis of genomic data, e.g. literature data from PubMed, annotation data from Entrez genes."),
  ]

  # Custom Code Execution Tool
  def execute_code_tool(code: str, timeout: int = 60, filename: str = "execution_file.py", work_dir: str = "work_dir", use_docker: bool = True, lang: str = "python"):
    return execute_code(code, timeout, filename, work_dir, use_docker, lang)

  code_execution_tool = Tool.from_function(
    func=execute_code_tool,
    name="Code Execution",
    description="Executes code in a docker container"
  )

  tools: list[BaseTool] = human_tools + browser_tools + github_tools + search + docs_tools + [code_execution_tool]
  return tools

	############# HELPERS ################
def _should_check(serialized_obj: dict) -> bool:
  # Only require approval on ShellTool.
  return serialized_obj.get("name") == "terminal"


def _approve(_input: str) -> bool:
  if _input == "echo 'Hello World'":
    return True
  msg = ("Do you approve of the following input? "
         "Anything except 'Y'/'Yes' (case-insensitive) will be treated as a no.")
  msg += "\n\n" + _input + "\n"
  resp = input(msg)
  return resp.lower() in ("yes", "y")


def get_human_input() -> str:
  """Placeholder for Slack input from user."""
  print("Insert your text. Enter 'q' or press Ctrl-D (or Ctrl-Z on Windows) to end.")
  contents = []
  while True:
    try:
      line = input()
    except EOFError:
      break
    if line == "q":
      break
    contents.append(line)
  return "\n".join(contents)