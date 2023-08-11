import os
from typing import List, Sequence, Tuple

import langchain
from agents import get_docstore_agent
from dotenv import load_dotenv
from langchain.agents import AgentType, Tool, initialize_agent, load_tools
from langchain.agents.agent_toolkits import PlayWrightBrowserToolkit
from langchain.agents.agent_toolkits.github.toolkit import GitHubToolkit
from langchain.agents.openai_functions_multi_agent.base import \
    OpenAIMultiFunctionsAgent
from langchain.agents.react.base import DocstoreExplorer
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
from langchain.chat_models.base import BaseChatModel
from langchain.docstore.base import Docstore
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.memory import (ConversationBufferMemory, ConversationSummaryBufferMemory)
from langchain.prompts import MessagesPlaceholder
from langchain.prompts.chat import (BaseMessagePromptTemplate, ChatPromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder)
from langchain.schema import AgentAction
from langchain.schema.language_model import BaseLanguageModel
from langchain.schema.messages import (AIMessage, BaseMessage, FunctionMessage, SystemMessage)
from langchain.tools.base import BaseTool
from langchain.tools.playwright.utils import \
    create_sync_playwright_browser  # A synchronous browser is available, though it isn't compatible with jupyter.
from langchain.tools.playwright.utils import create_async_playwright_browser
from langchain.utilities.github import GitHubAPIWrapper
from langchain.vectorstores import Qdrant
from llama_hub.github_repo import GithubClient, GithubRepositoryReader
from qdrant_client import QdrantClient
from tools import get_human_input, get_shell_tool, get_tools
from vector_db import count_tokens_and_cost, get_top_contexts_uiuc_chatbot

load_dotenv(override=True, dotenv_path='.env')

from langchain_experimental.autonomous_agents.autogpt.agent import AutoGPT
from langchain_experimental.autonomous_agents.baby_agi import BabyAGI
from langchain_experimental.plan_and_execute.agent_executor import \
    PlanAndExecute
from langchain_experimental.plan_and_execute.executors.agent_executor import \
    load_agent_executor
from langchain_experimental.plan_and_execute.planners.chat_planner import \
    load_chat_planner

os.environ["LANGCHAIN_TRACING"] = "true"  # If you want to trace the execution of the program, set to "true"
langchain.debug = False  # True for more detailed logs
VERBOSE = True
os.environ["LANGCHAIN_WANDB_TRACING"] = "true"  # TODO: https://docs.wandb.ai/guides/integrations/langchain
os.environ["WANDB_PROJECT"] = "langchain-tracing"  # optionally set your wandb settings or configs

from outer_loop_planner import fancier_trim_intermediate_steps

PR_BOT_SYSTEM_PROMPT = """You are a senior developer who helps others finish the work faster and to a higher quality than anyone else on the team. People often tag you on pull requests (PRs), and you will finish the PR to the best of your ability and commit your changes. If you're blocked or stuck, feel free to leave a comment on the PR and the rest of the team will help you out. Remember to keep trying, and reflecting on how you solved previous problems will usually help you fix the current issue. Please work hard, stay organized, and follow best practices.\nYou have access to the following tools:"""


class PR_Bot():

  def __init__(self, branch_name: str = ''):
    self.branch_name = branch_name
    self.github_api_wrapper = GitHubAPIWrapper(github_branch=branch_name)  # type: ignore
    self.pr_agent = self.make_bot()

  def make_bot(self):
    # LLMs
    SystemMessage(content=PR_BOT_SYSTEM_PROMPT)

    llm = ChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=3, request_timeout=60 * 3)  # type: ignore
    summarizer_llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo-0613", max_retries=3, request_timeout=60 * 3)  # type: ignore
    # MEMORY
    chat_history = MessagesPlaceholder(variable_name="chat_history")
    memory = ConversationSummaryBufferMemory(memory_key="chat_history", return_messages=True, llm=summarizer_llm, max_token_limit=2_000)

    # TOOLS
    toolkit = GitHubToolkit.from_github_api_wrapper(self.github_api_wrapper)
    github_tools: list[BaseTool] = toolkit.get_tools()
    human_tools: List[BaseTool] = load_tools(["human"], llm=llm, input_func=get_human_input)
    # todo: add tools for documentation search... unless I have a separate code author.
    # todo: tool for human. Maybe Arxiv too.

    return initialize_agent(
        tools=github_tools + human_tools,
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
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
            "prefix": PR_BOT_SYSTEM_PROMPT,
            # "extra_prompt_messages": [MessagesPlaceholder(variable_name="PR_BOT_SYSTEM_PROMPT")]
        })

  def on_new_pr(self, number: int):
    pr = self.github_api_wrapper.get_pull_request(number)
    print(f"PR {number}: {pr}")
    out = self.pr_agent.run(
        f"Please implement these changes by creating or editing the necessary files. First read all existing comments to better understand your task. Then read the existing files to see the progress. Finally implement any and all remaining code to make the project work as the commenter intended (but no need to open a new PR, your edits are automatically committed every time you use a tool to edit files). Feel free to ask for help, or leave a comment on the PR if you're stuck. Here's the latest PR: {str(pr)}"
    )
    print(f"👇FINAL ANSWER 👇\n{out}")

  def on_new_issue(self, number: int):
    out = self.pr_agent.run(
        f"Please implement these changes by creating or editing the necessary files. First read all existing comments to better understand your task. Then read any files in the repo that seem relevant. Finally, create a PR, then create or update all necessary files to implement the changes. Implement any and all remaining code to make the project work as the commenter intended. Feel free to ask for help, or leave a comment on the PR if you're stuck. Here's your latest assignment: {str(issue)}"
    )
    print(f"👇FINAL ANSWER 👇\n{out}")


from langchain.chat_models import ChatOpenAI
from langchain.prompts import (ChatPromptTemplate, HumanMessagePromptTemplate, PromptTemplate)
from langchain.prompts.chat import (ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate)


def convert_issue_to_branch_name(issue):

  system_template = "You are a helpful assistant that writes clear and concise github branch names for new pull requests."
  system_message_prompt = SystemMessagePromptTemplate.from_template(system_template)

  prompt = HumanMessagePromptTemplate.from_template(
      '''Given this issue, please return a single string that would be a suitable branch name on which to implement this feature request. Use common software development best practices to name the branch.
    Follow this formatting exactly:
    Issue: {"title": "Implement an Integral function in C", "body": "This request includes a placeholder for a C program that calculates an integral and a Makefile to compile it. Closes issue #6.", "comments": "[{'body': 'Please finish the implementation, these are just placeholder files.', 'user': 'KastanDay'}]
    Branch name: `add_integral_in_c`


    Issue: {issue}
    Branch name: `''')

  # Combine them into a ChatPromptTemplate
  chat_prompt = ChatPromptTemplate.from_messages([system_message_prompt, prompt])

  # Example usage
  formatted_messages = chat_prompt.format_messages(issue=str(issue))

  # Initialize the model
  llm = ChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=3, request_timeout=60 * 3)  # type: ignore
  output = llm(formatted_messages)
  print(f"SUGGESTED_BRANCH_NAME: <<{output.content}>>")
  print(f"Cleaned branch name: <<{strip_n_clean_text(output.content)}>>")

  return strip_n_clean_text(output.content)


def strip_n_clean_text(text):
  """
  Example:
    cleaned_text = strip_n_clean_text("Hello, World! This is an example.")
    print(cleaned_text)  # Output: "Hello_World_This_is_an_example"

  Returns:
      str: cleaned_text
  """
  # Split the text into words using a space as a separator
  words = text.split()

  # Remove any non-alphanumeric characters from each word
  cleaned_words = [''.join(c for c in word if c.isalnum()) for word in words]

  # Join the cleaned words with an underscore
  result = '_'.join(cleaned_words)

  return result


# make an embedding for every FUNCTION in the repo.

# get a list of all docstrings in the repo (w/ and w/out function signatures)

if __name__ == "__main__":
  # hard coded placeholders for now. TODO: watch PRs for changes via "Github App" api.
  b = PR_Bot(branch_name='bot-branch')
  b.on_new_pr(number=7)
