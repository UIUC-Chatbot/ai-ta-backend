######## GITHUB WEBHOOK HANDLERS ########
# from github import Github
import inspect
import logging
import os
import time
import traceback
import uuid
from dis import Instruction
from typing import Union

import github
import langchain
import ray
from github import Auth, GithubIntegration
from github.Issue import Issue
from github.PullRequest import PullRequest
from github.Repository import Repository
from langchain import hub
# from langchain.tools.github.utils import generate_branch_name
from langchain.utilities.github import GitHubAPIWrapper
from newrelic_telemetry_sdk import Log, LogClient, Span, SpanClient

from ai_ta_backend.agents import github_agent
from ai_ta_backend.agents.ml4bio_agent import WorkflowAgent
from ai_ta_backend.agents.utils import get_langsmith_trace_sharable_url

langchain.debug = False  # True for more detailed logs

MESSAGE_HANDLE_ISSUE_OPENED = f"""Thanks for opening a new issue! I'll now try to finish this implementation and open a PR for you to review.
    
{'You can monitor the [LangSmith trace here](https://smith.langchain.com/o/f7abb6a0-31f6-400c-8bc1-62ade4b67dc1/projects/p/c2ec9de2-71b4-4042-bea0-c706b38737e2).' if 'ML4Bio' in os.environ['LANGCHAIN_PROJECT'] else ''}

Feel free to comment in this thread to give me additional instructions, or I'll tag you in a comment if I get stuck.
If I think I'm successful I'll 'request your review' on the resulting PR. Just watch for emails while I work.
"""
log_client = LogClient(os.environ['NEW_RELIC_LICENSE_KEY'])

# app = newrelic.agent.application()

# @newrelic.agent.background_task() 
def handle_issue_opened(payload):
  """ This is the primary entry point to the app; Just open an issue!

  Args:
      payload (_type_): From github, see their webhook docs.
  """
  auth = Auth.AppAuth(
      os.environ["GITHUB_APP_ID"],
      os.environ["GITHUB_APP_PRIVATE_KEY"],
  )
  gi = GithubIntegration(auth=auth)
  installation = gi.get_installations()[0]
  g = installation.get_github_for_installation()

  issue = payload['issue']
  repo_name = payload["repository"]["full_name"]
  repo: Repository = g.get_repo(repo_name)
  base_branch = repo.get_branch(payload["repository"]["default_branch"])
  number = payload.get('issue').get('number')
  issue: Issue = repo.get_issue(number=number)
  langsmith_run_id = str(uuid.uuid4()) # for Langsmith 

  metadata = {"issue": str(issue), 'number': number, "repo_name": repo_name, "langsmith_run_id": langsmith_run_id}
  # logging.info(f"New issue created: #{number}", metadata)
  # logging.info(f"New issue created: #{number}. Metadata: {metadata}")

  log = Log(message=f"New issue created: #{number}", metadata=metadata)
  response = log_client.send(log)
  response.raise_for_status()

  try:

    # ! TODO: REENABLE: ROHAN's version of the bot.
    

    result_futures = []

    # 1. INTRO COMMENT
    # issue.create_comment(messageForNewIssues)
    result_futures.append(post_comment.remote(issue_or_pr=issue, text=MESSAGE_HANDLE_ISSUE_OPENED, time_delay_s=0))

    # 2. SHARABLE URL (in background)
    result_futures.append(post_sharable_url.remote(issue=issue, run_id_in_metadata=langsmith_run_id, time_delay_s=30))

    # 3. RUN BOT
    # bot = github_agent.GH_Agent.remote()
    prompt = hub.pull("kastanday/new-github-issue").format(issue_description=format_issue(issue))
    # result_futures.append(bot.launch_gh_agent.remote(prompt, active_branch=base_branch, run_id_in_metadata=langsmith_run_id))
    bot = WorkflowAgent(run_id_in_metadata=langsmith_run_id)
    result = bot.run(prompt)

    # COLLECT PARALLEL RESULTS
    for i in range(0, len(result_futures)): 
      ready, not_ready = ray.wait(result_futures)
      result = ray.get(ready[0])
      result_futures = not_ready
      if not result_futures:
        break

    # FIN: Conclusion & results comment
    ray.get(post_comment.remote(issue_or_pr=issue, text=str(result['output']), time_delay_s=0))
  except Exception as e:
    logging.error(f"❌❌ Error in {inspect.currentframe().f_code.co_name}: {e}\nTraceback:\n", traceback.print_exc())    
    err_str = f"Error in {inspect.currentframe().f_code.co_name}: {e}" + "\nTraceback\n```\n" + str(traceback.format_exc()) + "\n```"
    issue.create_comment(err_str)


def handle_pull_request_opened(payload):
  auth = Auth.AppAuth(
      os.environ["GITHUB_APP_ID"],
      os.environ["GITHUB_APP_PRIVATE_KEY"],
  )


  # TODO: 
  #     File "/Users/kastanday/code/ncsa/ai-ta/ai-ta-backend/ai_ta_backend/agents/github_webhook_handlers.py", line 120, in handle_pull_request_opened
  #     number = payload.get('issue').get('number') # AttributeError: 'NoneType' object has no attribute 'get'
  # AttributeError: 'NoneType' object has no attribute 'get'
  gi = GithubIntegration(auth=auth)
  installation = gi.get_installations()[0]
  g = installation.get_github_for_installation()

  repo_name = payload["repository"]["full_name"]
  repo = g.get_repo(repo_name)

  number = payload.get('issue').get('number') # TODO: AttributeError: 'NoneType' object has no attribute 'get'
  comment = payload.get('comment')
  comment_author = comment['user']['login']
  issue: Issue = repo.get_issue(number=number)
  comment_made_by_bot = True if comment.get('performed_via_github_app') else False
  pr: PullRequest = repo.get_pull(number=number)

  print(f"Received a pull request event for #{number}")
  try:
    branch_name = pr.head.ref
    messageForNewPRs = "Thanks for opening a new PR! I'll now try to finish this implementation and I'll comment if I get blocked or (WIP) 'request your review' if I think I'm successful. So just watch for emails while I work. Please comment to give me additional instructions."
    issue.create_comment(messageForNewPRs)
    
    print("LAUNCHING BOT")
    bot = WorkflowAgent()
    # pr_description = bot.github_api_wrapper.get_pull_request(number)
    # instruction = f"Please implement these changes by creating or editing the necessary files. First read all existing comments to better understand your task. Then read the existing files to see the progress. Finally implement any and all remaining code to make the project work as the commenter intended (but no need to open a new PR, your edits are automatically committed every time you use a tool to edit files). Feel free to ask for help, or leave a comment on the PR if you're stuck. Here's the latest PR: {str(pr_description)}"
    # result = bot.launch_gh_agent(instruction, active_branch=branch_name)
    result = bot.run(comment)
    issue.create_comment(result)
  except Exception as e:
    print(f"Error: {e}")
    logging.error(f"❌❌ Error in {inspect.currentframe().f_code.co_name}: {e}\nTraceback:\n", traceback.print_exc())
    err_str = f"Error in {inspect.currentframe().f_code.co_name}: {e}" + "\nTraceback\n```\n" + str(traceback.format_exc()) + "\n```"
    issue.create_comment(f"Bot hit a runtime exception during execution. TODO: have more bots debug this.\nError:{err_str}")



def handle_comment_opened(payload):
  """Note: In Github API, PRs are just issues with an extra PR object. Issue numbers and PR numbers live in the same space.
  Args:
      payload (_type_): _description_
  """
  auth = Auth.AppAuth(
      os.environ["GITHUB_APP_ID"],
      os.environ["GITHUB_APP_PRIVATE_KEY"],
  )
  # ensure the author is not lil-jr-dev bot.
  gi = GithubIntegration(auth=auth)
  installation = gi.get_installations()[0]
  g = installation.get_github_for_installation()

  repo_name = payload["repository"]["full_name"]
  repo = g.get_repo(repo_name)
  number = payload.get('issue').get('number')
  comment = payload.get('comment')
  comment_author = comment['user']['login']
  # issue_response = payload.get('issue')
  issue: Issue = repo.get_issue(number=number)
  is_pr = True if payload.get('issue').get('pull_request') else False
  comment_made_by_bot = True if comment.get('performed_via_github_app') else False

  # DON'T REPLY TO SELF (inf loop)
  if comment_author == 'lil-jr-dev[bot]':
    print(f"Comment author is {comment_author}, no reply...")
    return

  print("Comment author: ", comment['user']['login'])
  try:
    if is_pr:
      print("🥵🥵🥵🥵🥵🥵🥵🥵🥵🥵 COMMENT ON A PR")
      pr: PullRequest = repo.get_pull(number=number)
      branch_name = pr.head.ref
      print(f"Head branch_name: {branch_name}")
      
      # LAUNCH NEW PR COMMENT BOT 
      messageForNewPRs = "Thanks for commenting on this PR!! I'll now try to finish this implementation and I'll comment if I get blocked or (WIP) 'request your review' if I think I'm successful. So just watch for emails while I work. Please comment to give me additional instructions."
      issue.create_comment(messageForNewPRs)

      bot = github_agent.GH_Agent(branch_name=branch_name)
      instruction = f"Please complete this work-in-progress pull request (PR number {number}) by implementing the changes discussed in the comments. You can update and create files to make all necessary changes. First use read_file to read any files in the repo that seem relevant. Then, when you're ready, start implementing changes by creating and updating files. Implement any and all remaining code to make the project work as the commenter intended. You don't have to commit your changes, they are saved automaticaly on every file change. The last step is to complete the PR and leave a comment tagging the relevant humans for review, or list any concerns or final changes necessary in your comment. Feel free to ask for help, or leave a comment on the PR if you're stuck.  Here's your latest PR assignment: {format_issue(issue)}"
      result = bot.launch_gh_agent(instruction, active_branch=branch_name)
      issue.create_comment(result)
    else:
      # IS COMMENT ON ISSUE
      print("🤗🤗🤗🤗🤗🤗🤗🤗🤗🤗 THIS IS A COMMENT ON AN ISSUE")
      messageForIssues = "Thanks for opening a new or edited comment on an issue! We'll try to implement changes per your updated request, and will attempt to contribute to any existing PRs related to this or open a new PR if necessary."
      issue.create_comment(messageForIssues)

      # todo: refactor with new branch name creation
      unique_branch_name = ensure_unique_branch_name(repo, "bot-branch")
      # bot = github_agent.GH_Agent()
      # issue_description = bot.github_api_wrapper.get_issue(number)
      # instruction = f"Your boss has just commented on the Github issue that was assigned to you, please review their latest comments and complete the work assigned. There may or may not be an open PR related to this already. Open or complete that PR by implementing the changes discussed in the comments. You can update and create files to make all necessary changes. First use read_file to read any files in the repo that seem relevant. Then, when you're ready, start implementing changes by creating and updating files. Implement any and all remaining code to make the project work as the commenter intended. You don't have to commit your changes, they are saved automatically on every file change. The last step is to complete the PR and leave a comment tagging the relevant humans for review, or list any concerns or final changes necessary in your comment. Feel free to ask for help, or leave a comment on the PR if you're stuck. Here's your latest PR assignment: {str(issue_description)}"
      # result = bot.launch_gh_agent(instruction, active_branch=unique_branch_name)
      bot = WorkflowAgent()
      result = bot.run(comment)
      issue.create_comment(result)
  except Exception as e:
    logging.error(f"❌❌ Error in {inspect.currentframe().f_code.co_name}: {e}\nTraceback:\n", traceback.print_exc())    
    err_str = f"Error in {inspect.currentframe().f_code.co_name}: {e}" + "\nTraceback\n```\n" + str(traceback.format_exc()) + "\n```"
    issue.create_comment(f"Bot hit a runtime exception during execution. TODO: have more bots debug this.\nError: {err_str}")

@ray.remote
def post_comment(issue_or_pr: Union[Issue, PullRequest], text: str, time_delay_s: int):
  """A helper method to post a comment after a delay.

  Args:
      issue_or_pr (Union[Issue, PullRequest]): The full object.
      text (str): Text to be posted as a comment by Lil-Jr-Dev[bot]
      time_delay_s (int): Time delay before running
  """
  time.sleep(time_delay_s)
  issue_or_pr.create_comment(str(text))

def extract_key_info_from_issue_or_pr(issue_or_pr: Union[Issue, PullRequest]):
  """Filter out useless info, format nicely. Especially filter out comment if comment 'performed_via_github_app'.
  comment_made_by_bot = True if comment.get('performed_via_github_app') else False

  Maybe grab other issues if they're referenced.

  Args:
      issue_or_pr (Union[Issue, PullRequest]): Full object of the issue or PR.
  Returns: 
      full_description: str
  """
  
  pass


@ray.remote
def post_sharable_url(issue, run_id_in_metadata, time_delay_s):
  sharable_url = get_langsmith_trace_sharable_url(run_id_in_metadata, time_delay_s=time_delay_s)
  text = f"👉 [Follow the bot's progress in real time on LangSmith]({sharable_url})."
  ray.get(post_comment.remote(issue_or_pr=issue, text=text, time_delay_s=0))


def format_issue(issue):
  return f"""Title: {issue.title}.
{f"Existing PR addressing issue: {issue._pull_request}" if str(issue._pull_request) != "NotSet" else ""}
{f"Opened by user: {issue.user.login}" if type(issue.user) == github.NamedUser.NamedUser else ''}
Body: {issue.body}"""