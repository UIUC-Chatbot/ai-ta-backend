"""
Env for Kastan: openai_3 or flask10_py10
"""

import inspect
import logging
import os
import traceback
import uuid
from typing import List, Sequence, Tuple

import langchain
# from ai_ta_backend.agents import get_docstore_agent
from dotenv import load_dotenv
from github import GithubException
from github.Issue import Issue
from langchain.agents import (AgentExecutor, AgentType, Tool, initialize_agent,
                              load_tools)
from langchain.agents.agent_toolkits import PlayWrightBrowserToolkit
from langchain.agents.agent_toolkits.github.toolkit import GitHubToolkit
from langchain.agents.openai_functions_multi_agent.base import \
    OpenAIMultiFunctionsAgent
from langchain.agents.react.base import DocstoreExplorer
from langchain.callbacks.manager import tracing_v2_enabled
from langchain.chains import RetrievalQA
from langchain.chat_models import AzureChatOpenAI, ChatOpenAI
from langchain.chat_models.base import BaseChatModel
from langchain.docstore.base import Docstore
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.memory import (ConversationBufferMemory,
                              ConversationSummaryBufferMemory)
from langchain.prompts import (ChatPromptTemplate, HumanMessagePromptTemplate,
                               MessagesPlaceholder, PromptTemplate)
from langchain.prompts.chat import (BaseMessagePromptTemplate,
                                    ChatPromptTemplate,
                                    HumanMessagePromptTemplate,
                                    MessagesPlaceholder,
                                    SystemMessagePromptTemplate)
from langchain.schema import AgentAction
from langchain.schema.language_model import BaseLanguageModel
from langchain.schema.messages import (AIMessage, BaseMessage, FunctionMessage,
                                       SystemMessage)
from langchain.tools.base import BaseTool
from langchain.tools.playwright.utils import \
    create_sync_playwright_browser  # A synchronous browser is available, though it isn't compatible with jupyter.
from langchain.tools.playwright.utils import create_async_playwright_browser
from langchain.utilities.github import GitHubAPIWrapper
from langchain.vectorstores import Qdrant
# from langchain_experimental.autonomous_agents.autogpt.agent import AutoGPT
# from langchain_experimental.autonomous_agents.baby_agi import BabyAGI
from langchain_experimental.plan_and_execute.agent_executor import \
    PlanAndExecute
from langchain_experimental.plan_and_execute.executors.agent_executor import \
    load_agent_executor
from langchain_experimental.plan_and_execute.planners.chat_planner import \
    load_chat_planner
from langsmith import Client
from qdrant_client import QdrantClient
from typing_extensions import runtime

from ai_ta_backend.agents.tools import (get_human_input, get_shell_tool,
                                        get_tools)

# load_dotenv(override=True, dotenv_path='.env')

os.environ["LANGCHAIN_TRACING"] = "true"  # If you want to trace the execution of the program, set to "true"
os.environ["LANGCHAIN_WANDB_TRACING"] = "false"  # TODO: https://docs.wandb.ai/guides/integrations/langchain

langchain.debug = False  # True for more detailed logs
VERBOSE = True

from ai_ta_backend.agents.outer_loop_planner import \
    fancier_trim_intermediate_steps

GH_Agent_SYSTEM_PROMPT = """You are a senior developer who helps others finish the work faster and to a higher quality than anyone else on the team. People often tag you on pull requests (PRs), and you will finish the PR to the best of your ability and commit your changes. If you're blocked or stuck, feel free to leave a comment on the PR and the rest of the team will help you out. Remember to keep trying, and reflecting on how you solved previous problems will usually help you fix the current issue. Please work hard, stay organized, and follow best practices.\nYou have access to the following tools:"""


class GH_Agent():

  def __init__(self, branch_name: str = ''):
    self.branch_name = branch_name
    self.github_api_wrapper = GitHubAPIWrapper(active_branch=branch_name, github_base_branch='main')  # type: ignore
    self.pr_agent: AgentExecutor = self.make_bot()

  def make_bot(self):
    # LLMs
    SystemMessage(content=GH_Agent_SYSTEM_PROMPT)


    if os.environ['OPENAI_API_TYPE'] != 'azure':
      llm = ChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=3, request_timeout=60 * 3)  # type: ignore
      human_llm = ChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=3, request_timeout=60 * 3)  # type: ignore
      summarizer_llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo-0613", max_retries=3, request_timeout=60 * 3)  # type: ignore
    else: 
      llm = AzureChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=3, request_timeout=60 * 3, deployment_name=os.environ['AZURE_OPENAI_ENGINE'])  # type: ignore
      human_llm = AzureChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=3, request_timeout=60 * 3, deployment_name=os.environ['AZURE_OPENAI_ENGINE'])  # type: ignore
      summarizer_llm = AzureChatOpenAI(temperature=0, model="gpt-3.5-turbo-0613", max_retries=3, request_timeout=60 * 3, deployment_name=os.environ['AZURE_OPENAI_ENGINE'])  # type: ignore

    # MEMORY
    chat_history = MessagesPlaceholder(variable_name="chat_history")
    memory = ConversationSummaryBufferMemory(memory_key="chat_history", return_messages=True, llm=summarizer_llm, max_token_limit=2_000)

    # TOOLS
    toolkit: GitHubToolkit = GitHubToolkit.from_github_api_wrapper(self.github_api_wrapper)
    github_tools: list[BaseTool] = toolkit.get_tools()
    human_tools: List[BaseTool] = load_tools(["human"], llm=human_llm, input_func=get_human_input)
    # todo: add tools for documentation search... unless I have a separate code author.
    # todo: tool for human. Maybe Arxiv too.

    return initialize_agent(
        tools=github_tools + human_tools,
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        # agent=AgentType.OPENAI_MULTI_FUNCTIONS,
        verbose=VERBOSE,
        handle_parsing_errors=True,  # or pass a function that accepts the error and returns a string
        max_iterations=30,
        max_execution_time=None,
        early_stopping_method='generate',
        memory=memory,
        trim_intermediate_steps=fancier_trim_intermediate_steps,
        agent_kwargs={
            "memory_prompts": [chat_history],
            "input_variables": ["input", "agent_scratchpad", "chat_history"],
            "prefix": GH_Agent_SYSTEM_PROMPT,
            # pretty sure this is wack: # "extra_prompt_messages": [MessagesPlaceholder(variable_name="GH_Agent_SYSTEM_PROMPT")] 
        })

  def launch_gh_agent(self, instruction: str, active_branch='bot-branch'):
    # self.github_api_wrapper.set_active_branch(active_branch)
    return self.bot_runner_with_retries(self.pr_agent, instruction)

  def bot_runner_with_retries(self, bot: AgentExecutor, run_instruction, total_retries=1):
    """Runs the given bot with attempted retries. First prototype.
    """
    langsmith_client = Client()
    print("LIMITING TOTAL RETRIES TO 0, wasting too much money....")
    runtime_exceptions = []
    result = ''
    for num_retries in range(1,total_retries+1):
      with tracing_v2_enabled(project_name="ML4Bio", tags=['lil-jr-dev', str(run_id)]) as cb:
        try:
          #! MAIN RUN FUNCTION
          if len(runtime_exceptions) >= 1:
            warning_to_bot = f"Keep in mind {num_retries} previous bots have tried to solve this problem faced a runtime error. Please learn from their mistakes, focus on making sure you format your requests for tool use correctly. Here's a list of their previous runtime errors: {str(runtime_exceptions)}"
            result = bot.run(f"{run_instruction}\n{warning_to_bot}")
          else:
            result = bot.run(f"{run_instruction}")
          break # no error, so break retry loop

        except Exception as e:
          print("-----------❌❌❌❌------------START OF ERROR-----------❌❌❌❌------------")
          print(f"Error in {inspect.currentframe().f_code.co_name}: {e}") # print function name in error.
          print(f"Traceback:")
          print(traceback.print_exc())

          runtime_exceptions.append(traceback.format_exc())
          print(f"❌❌❌ num_retries: {num_retries}. Bot hit runtime exception: {e}")
        finally:
          # Langsmith: can only get the URL after the bot starts..... 
          private_url = cb.get_run_url()
          logging.info(f'private_url: {private_url}')
          # TODO: list runs, get runID, share run, comment on issue.
          # sharable_url = langsmith_client.share_run(run_id=run_id)
          # logging.info(f'⭐️ sharable_url: {sharable_url}')
    
    if result == '':
      formatted_exceptions = '\n'.join([f'```\n{exc}\n```' for exc in runtime_exceptions])
      result = f"{total_retries} agents ALL FAILED with runtime exceptions: \n{formatted_exceptions}"
    print(f"👇FINAL ANSWER 👇\n{result}")
    return result


if __name__ == "__main__":
  print("No code.")
