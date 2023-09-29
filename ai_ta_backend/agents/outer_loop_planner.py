'''
## USAGE

In Notebooks, since they have their own eventloop:
  import nest_asyncio
  nest_asyncio.apply()

On the command line

'''

import asyncio
import os
import threading
import token
from typing import List, Sequence, Tuple

import langchain
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
from langchain.prompts import MessagesPlaceholder
from langchain.prompts.chat import (BaseMessagePromptTemplate,
                                    ChatPromptTemplate,
                                    HumanMessagePromptTemplate,
                                    MessagesPlaceholder)
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
from qdrant_client import QdrantClient

# Our own imports 
from ai_ta_backend.agents.agents import get_docstore_agent
from ai_ta_backend.agents.tools import get_shell_tool, get_tools
from ai_ta_backend.agents.vector_db import (count_tokens_and_cost,
                                            get_top_contexts_uiuc_chatbot)

load_dotenv(override=True, dotenv_path='.env')


# from langchain_experimental.autonomous_agents.autogpt.agent import AutoGPT
# from langchain_experimental.autonomous_agents.baby_agi import BabyAGI
from langchain_experimental.plan_and_execute.agent_executor import \
    PlanAndExecute
from langchain_experimental.plan_and_execute.executors.agent_executor import \
    load_agent_executor
from langchain_experimental.plan_and_execute.planners.chat_planner import \
    load_chat_planner

os.environ["LANGCHAIN_TRACING"] = "true"  # If you want to trace the execution of the program, set to "true"
langchain.debug = False  # True for more detailed logs
VERBOSE = True
os.environ["LANGCHAIN_WANDB_TRACING"] = "true" # TODO: https://docs.wandb.ai/guides/integrations/langchain
os.environ["WANDB_PROJECT"] = "langchain-tracing"  # optionally set your wandb settings or configs


class OuterLoopPlanner:

  def __init__(self):
    print("Before qdrant")
    self.qdrant_client = QdrantClient(url=os.getenv('QDRANT_URL'), api_key=os.getenv('QDRANT_API_KEY'))

    print("Before creating vectorstore")
    self.langchain_docs_vectorstore = Qdrant(
        client=self.qdrant_client,
        collection_name=os.getenv('QDRANT_LANGCHAIN_DOCS'),  # type: ignore
        embeddings=OpenAIEmbeddings())  # type: ignore

    # print("Before creating vectorstore")
    # self.langchain_docs_vectorstore = Qdrant(
    #     client=self.qdrant_client,
    #     collection_name=os.getenv('QDRANT_LANGCHAIN_DOCS'),  # type: ignore
    #     embeddings=OpenAIEmbeddings())  # type: ignore

    # write a function to search against the UIUC database
    get_top_contexts_uiuc_chatbot(search_query='', course_name='', token_limit=8_000)

    print("after __init__")
    # todo: try babyagi
    # BabyAGI()

  def autogpt_babyagi(self, llm: BaseChatModel, tools: List[BaseTool], prompt: str, memory=None):
    # langchain_retriever = RetrievalQA.from_chain_type(llm=ChatOpenAI(model='gpt-4-0613'), chain_type="stuff", retriever=self.langchain_docs_vectorstore.as_retriever())

    autogpt = AutoGPT.from_llm_and_tools(
        ai_name='coding assistant',
        ai_role='ML engineer',
        tools=tools,
        llm=llm,
        human_in_the_loop=True,
        memory=self.langchain_docs_vectorstore.as_retriever(),
    )
    goals: List[str] = [prompt]
    autogpt.run(goals=goals)


def openai_functions_agent(llm, tools):
  system_message = SystemMessage(content='''You debug broken code. Use JSON formatting to return the result. Always show before and after.
  Format like this
  # TODO steal from Aider format for before and after. 
  filename_to_edit.file_extension
  <<<<<<< ORIGINAL
  buggy code
  =======
  fixed code
  >>>>>>> UPDATED
  ''')
  # extra_prompt_messages = list(BaseMessagePromptTemplate('''TODO'''))
  # extra_prompt_messages = 'things'

  # todo: use this initialization function
  agent = initialize_agent()

  prompt = OpenAIMultiFunctionsAgent.create_prompt(system_message=system_message,)  # extra_prompt_messages=extra_prompt_messages
  agent = OpenAIMultiFunctionsAgent(llm=llm, tools=tools, prompt=prompt)
  agent.plan()


def experimental_main(llm: BaseLanguageModel, tools: Sequence[BaseTool], memory, prompt: str):
  input = {'input': prompt}
  system_prompt = """"""
  PLANNER_SYSTEM_PROMPT = (
      "Let's first understand the problem and devise a plan to solve the problem."
      " Please output the plan starting with the header 'Plan:' "
      "and then followed by a numbered list of steps. "
      "Please make the plan the minimum number of steps required "
      "to accurately complete the task. If the task is a question, "
      "the final step should almost always be 'Given the above steps taken, "
      "please respond to the users original question'. "
      "If anything is majorly missing preventing you from being confident in the plan, please ask the human for clarification."  # new
      "At the end of your plan, say '<END_OF_PLAN>'")

  planner = load_chat_planner(llm)
  executor = load_agent_executor(
      llm=llm,
      tools=list(tools),
      verbose=True,
      include_task_in_prompt=False,
  )

  agent = PlanAndExecute(
      planner=planner,
      executor=executor,
  )
  response = agent.run(input=input)
  print(f"👇FINAL ANSWER 👇\n{response}")


def main(llm: BaseLanguageModel, tools: Sequence[BaseTool], memory, prompt: str):

  # custom agent for debugging... but we can have multiple types of bugs. Code, knowing what to do... knowing what APIs to use.
  # lets focus on code debugging

  # 1. Edit PRs Bot (needs to be given the branch name, and just works on that branch)
    # Needs some global variable for branch name, inside the GithubAPI Wrapper. Do this when enstantiating it. 
  # 2. Create PRs Bot (basically standard, with a prompt of "read latest issue and implement as a new PR")


  agent_chain = initialize_agent(
      tools=tools,
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
          "input_variables": ["input", "agent_scratchpad", "chat_history"]
      })

  # response = await agent_chain.arun(input="Ask the user what they're interested in learning about on Langchain, then Browse to blog.langchain.dev and summarize the text especially whatever is relevant to the user, please.")
  response = agent_chain.run(input=prompt)
  print(f"👇FINAL ANSWER 👇\n{response}")


def trim_intermediate_steps(steps: List[Tuple[AgentAction, str]]) -> List[Tuple[AgentAction, str]]:
  """
  Trim the history of Agent steps to fit within the token limit.

  AgentAction has: 
  tool: str
      The name of the Tool to execute.
  tool_input: Union[str, dict]
      The input to pass in to the Tool.
  log: str

  Args:
      steps (List[Tuple[AgentAction, str]]): A list of agent actions and associated strings.

  Returns:
      List[Tuple[AgentAction, str]]: A list of the most recent actions that fit within the token limit.
  """

  token_limit = 4_000
  total_tokens = 0
  selected_steps = []

  for step in reversed(steps):
    action, _ = step
    tokens_in_action = sum(count_tokens_and_cost(str(getattr(action, attr)))[0] for attr in ['tool', 'tool_input', 'log'])
    total_tokens += tokens_in_action

    if total_tokens <= token_limit:
      selected_steps.insert(0, step)
    else:
      break

  print("In trim_latest_3_actions!! 👇👇👇👇👇👇👇👇👇👇👇👇👇👇 ")
  print(selected_steps)
  print("Tokens used: ", total_tokens)
  print("👆👆👆👆👆👆👆👆👆👆👆👆👆")
  return selected_steps


def fancier_trim_intermediate_steps(steps: List[Tuple[AgentAction, str]]) -> List[Tuple[AgentAction, str]]:
  """
    Trim the history of Agent steps to fit within the token limit.
    If we're over the limit, start removing the logs from the oldest actions first. then remove the tool_input from the oldest actions. then remove the tool from the oldest actions. then remove the oldest actions entirely. To remove any of these, just set it as an empty string.

    Args:
        steps (List[Tuple[AgentAction, str]]): A list of agent actions and associated strings.

    Returns:
        List[Tuple[AgentAction, str]]: A list of the most recent actions that fit within the token limit.
    """

  def count_tokens(action: AgentAction) -> int:
    return sum(count_tokens_and_cost(str(getattr(action, attr)))[0] for attr in ['tool', 'tool_input', 'log'])

  token_limit = 4_000
  total_tokens = sum(count_tokens(action) for action, _ in steps)

  # Remove the logs if over the limit
  if total_tokens > token_limit:
    for action, _ in steps:
      action.log = ''
      total_tokens = sum(count_tokens(action) for action, _ in steps)
      if total_tokens <= token_limit:
        break

  # Remove the tool_input if over the limit
  if total_tokens > token_limit:
    for action, _ in steps:
      action.tool_input = ''
      total_tokens = sum(count_tokens(action) for action, _ in steps)
      if total_tokens <= token_limit:
        break

  # Remove the tool if over the limit
  if total_tokens > token_limit:
    for action, _ in steps:
      action.tool = ''
      total_tokens = sum(count_tokens(action) for action, _ in steps)
      if total_tokens <= token_limit:
        break

  # Remove the oldest actions if over the limit
  while total_tokens > token_limit:
    steps.pop(0)
    total_tokens = sum(count_tokens(action) for action, _ in steps)

  # print("In fancier_trim_latest_3_actions!! 👇👇👇👇👇👇👇👇👇👇👇👇👇👇 ")
  # print(steps)
  # print("Tokens used: ", total_tokens)
  # print("👆👆👆👆👆👆👆👆👆👆👆👆👆")
  return steps

# agents.agent.LLMSingleActionAgent
# 1. collect relevant code documentation
# 2. collect relevant code files from github
# 3. Propose a change to the code and commit it into a new branch on github

# Input: I ask it to write some code in a specific library (Langchain). It writes it.
# 1. Find docs
# 2. Write code
#   a. just return code or Decide if it's reasonable to execute & debug OR

if __name__ == "__main__":
  # LLM
  llm = ChatOpenAI(temperature=0, model="gpt-4-0613", max_retries=3, request_timeout=60 * 3)  # type: ignore
  summarizer_llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo-0613", max_retries=3, request_timeout=60 * 3)  # type: ignore

  # TOOLS
  tools = get_tools(llm, sync=True)

  # MEMORY
  chat_history = MessagesPlaceholder(variable_name="chat_history")
  # memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
  memory = ConversationSummaryBufferMemory(memory_key="chat_history", return_messages=True, llm=summarizer_llm, max_token_limit=2_000)

  # can't do keyboard input
  # prompt = "Browse to https://lumetta.web.engr.illinois.edu/120-binary/120-binary.html and complete the first challenge using the keyboard to enter information, please."

  # prompt = "Please find the Python docs for LangChain, then write a function that takes a list of strings and returns a list of the lengths of those strings."
  # prompt = "Please find the Python docs for LangChain to help you write an example of a Retrieval QA chain, or anything like that which can answer questions against a corpus of documents. Return just a single example in Python, please."
  # ✅ worked with both Langchain PlanExecuteAgents. But NOT AutoGPT because it struggled with the internet.
  # prompt = "Write an example of making parallel requests to an API with exponential backoff, or anything like that. Return just a single example in Python, please."
  # prompt = "Close the issue about the README.md because it was solved by the most recent PR. When you close the issue, reference the PR in the issue comment, please."
  # prompt = "Merge the PR about the web scraping if it looks good to you"
  # prompt = "Implement the latest issue about a standard RNA Seq pipeline. Please open a PR with the code changes, do the best you can."
  prompt = "Implement the latest issue about a Integral function in C. Please open a PR with the code changes, do the best you can."
  # prompt = "Read PR 7 and finish the implementation that began there. Create the files with the finished implementation and create a new PR to submit your work."


  main(llm=llm, tools=tools, memory=memory, prompt=prompt)
  # experimental_main(llm=llm, tools=tools, memory=memory, prompt=prompt)

  # o = OuterLoopPlanner()
  # o.autogpt_babyagi(llm=llm, tools=tools, prompt=prompt)
