import os
from typing import List, Sequence, Tuple

import langchain
# from ai_ta_backend.agents import get_docstore_agent
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
from langchain_experimental.autonomous_agents.autogpt.agent import AutoGPT
from langchain_experimental.autonomous_agents.baby_agi import BabyAGI
from langchain_experimental.plan_and_execute.agent_executor import \
    PlanAndExecute
from langchain_experimental.plan_and_execute.executors.agent_executor import \
    load_agent_executor
from langchain_experimental.plan_and_execute.planners.chat_planner import \
    load_chat_planner
from qdrant_client import QdrantClient
from typing_extensions import runtime

from ai_ta_backend.agents.tools import (get_human_input, get_shell_tool,
                                        get_tools)
from ai_ta_backend.agents.vector_db import (count_tokens_and_cost,
                                            get_top_contexts_uiuc_chatbot)

# load_dotenv(override=True, dotenv_path='.env')

# os.environ["LANGCHAIN_TRACING"] = "true"  # If you want to trace the execution of the program, set to "true"
# os.environ["LANGCHAIN_WANDB_TRACING"] = "true"  # TODO: https://docs.wandb.ai/guides/integrations/langchain
# os.environ["WANDB_PROJECT"] = "langchain-tracing"  # optionally set your wandb settings or configs
os.environ["LANGCHAIN_TRACING"] = "false"  # If you want to trace the execution of the program, set to "true"
os.environ["LANGCHAIN_WANDB_TRACING"] = "false"  # TODO: https://docs.wandb.ai/guides/integrations/langchain
os.environ["WANDB_PROJECT"] = ""  # optionally set your wandb settings or configs

langchain.debug = False  # True for more detailed logs
VERBOSE = True

from ai_ta_backend.agents.outer_loop_planner import \
    fancier_trim_intermediate_steps

GH_Agent_SYSTEM_PROMPT = """You are a senior developer who helps others finish the work faster and to a higher quality than anyone else on the team. People often tag you on pull requests (PRs), and you will finish the PR to the best of your ability and commit your changes. If you're blocked or stuck, feel free to leave a comment on the PR and the rest of the team will help you out. Remember to keep trying, and reflecting on how you solved previous problems will usually help you fix the current issue. Please work hard, stay organized, and follow best practices.\nYou have access to the following tools:"""


class GH_Agent():

  def __init__(self, branch_name: str = ''):
    self.branch_name = branch_name
    self.github_api_wrapper = GitHubAPIWrapper(activate_branch=branch_name)  # type: ignore
    self.pr_agent = self.make_bot()

  def make_bot(self):
    # LLMs
    SystemMessage(content=GH_Agent_SYSTEM_PROMPT)

    llm = ChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=3, request_timeout=60 * 3)  # type: ignore
    human_llm = ChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=3, request_timeout=60 * 3)  # type: ignore
    summarizer_llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo-0613", max_retries=3, request_timeout=60 * 3)  # type: ignore
    # MEMORY
    chat_history = MessagesPlaceholder(variable_name="chat_history")
    memory = ConversationSummaryBufferMemory(memory_key="chat_history", return_messages=True, llm=summarizer_llm, max_token_limit=2_000)

    # TOOLS
    toolkit = GitHubToolkit.from_github_api_wrapper(self.github_api_wrapper)
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
    self.github_api_wrapper.set_active_branch(active_branch)
    return self.bot_runner_with_retries(self.pr_agent, instruction)

  def set_active_branch(self, branch_name):
    self.github_api_wrapper.set_active_branch(branch_name)

  # TODO: these 3 functions can probably be consolidated to "launch GH agent w/ custom prompt, make the caller's responsibility to use GH agents for a task"
  # def on_new_pr(self, number: int):
  #   pr = self.github_api_wrapper.get_pull_request(number)
  #   print(f"PR {number}: {pr}")
  #   instruction = f"Please implement these changes by creating or editing the necessary files. First read all existing comments to better understand your task. Then read the existing files to see the progress. Finally implement any and all remaining code to make the project work as the commenter intended (but no need to open a new PR, your edits are automatically committed every time you use a tool to edit files). Feel free to ask for help, or leave a comment on the PR if you're stuck. Here's the latest PR: {str(pr)}"
  #   self.bot_runner_with_retries(self.pr_agent, instruction)

  # def on_new_issue(self, number: int):
  #   issue = self.github_api_wrapper.get_issue(number)
  #   instruction = f"Please implement these changes by creating or editing the necessary files. First use read_file to read any files in the repo that seem relevant. Then, when you're ready, start implementing changes by creating and updating files. Implement any and all remaining code to make the project work as the commenter intended. The last step is to create a PR with a clear and concise title and description, list any concerns or final changes necessary in the PR body. Feel free to ask for help, or leave a comment on the PR if you're stuck.  Here's your latest assignment: {str(issue)}"
  #   self.bot_runner_with_retries(self.pr_agent, instruction)
  
  # def on_pr_comment(self, number: int):
  #   issue = self.github_api_wrapper.get_issue(number)
  #   instruction = f"Please complete this work-in-progress pull request by implementing the changes discussed in the comments. You can update and create files to make all necessary changes. First use read_file to read any files in the repo that seem relevant. Then, when you're ready, start implementing changes by creating and updating files. Implement any and all remaining code to make the project work as the commenter intended. You don't have to commit your changes, they are saved automaticaly on every file change. The last step is to complete the PR and leave a comment tagging the relevant humans for review, or list any concerns or final changes necessary in your comment. Feel free to ask for help, or leave a comment on the PR if you're stuck.  Here's your latest PR assignment: {str(issue)}"
  #   self.bot_runner_with_retries(self.pr_agent, instruction)
  
  def bot_runner_with_retries(self, bot, run_instruction, total_retries=3):
    """Runs the given bot with attempted retries. First prototype.
    """  
    runtime_exceptions = []
    result = ''
    for num_retries in range(1,total_retries+1):
      warning_to_bot = f"Keep in mind the last bot that tried to solve this problem faced a runtime error. Please learn from the mistakes of the last bot. The last bot's error was: {str(runtime_exceptions)}"
      if len(runtime_exceptions) > 1:
        warning_to_bot = f"Keep in mind {num_retries} previous bots have tried to solve this problem faced a runtime error. Please learn from their mistakes, focus on making sure you format your requests for tool use correctly. Here's a list of their previous runtime errors: {str(runtime_exceptions)}"
      
      try:
          result = bot.run(f"{run_instruction}\n{warning_to_bot}")
          bot.intermediate_steps
      except Exception as e:
          runtime_exceptions.append(e)
          print(f"❌❌❌ num_retries: {num_retries}. Bot hit runtime exception: {e}")
    if result == '':
      result = f"{total_retries} agents ALL FAILED with runtime exceptions: runtime_exceptions: {runtime_exceptions}"
    print(f"👇FINAL ANSWER 👇\n{result}")
    return result


def convert_issue_to_branch_name(issue):

  system_template = "You are a helpful assistant that writes clear and concise github branch names for new pull requests."
  system_message_prompt = SystemMessagePromptTemplate.from_template(system_template)

  example_issue = {"title": "Implement an Integral function in C", "body": "This request includes a placeholder for a C program that calculates an integral and a Makefile to compile it. Closes issue #6.", "comments": [{'body': 'Please finish the implementation, these are just placeholder files.', 'user': 'KastanDay'}]}

  prompt = HumanMessagePromptTemplate.from_template(
      '''Given this issue, please return a single string that would be a suitable branch name on which to implement this feature request. Use common software development best practices to name the branch.
    Follow this formatting exactly:
    Issue: {example_issue}
    Branch name: `add_integral_in_c`


    Issue: {issue}
    Branch name: `''')

  # Combine into a Chat conversation
  chat_prompt = ChatPromptTemplate.from_messages([system_message_prompt, prompt])
  formatted_messages = chat_prompt.format_messages(issue=str(issue), example_issue=str(example_issue))

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
  cleaned_words = [''.join(c for c in word if c.isalnum() or c == '_') for word in words]

  # Join the cleaned words with an underscore
  result = '_'.join(cleaned_words)

  return result


if __name__ == "__main__":
  print("No code.")
  # hard coded placeholders for now. TODO: watch PRs for changes via "Github App" api.
  # b = GH_Agent(branch_name='bot-branch')
  # b.on_new_pr(number=7)
