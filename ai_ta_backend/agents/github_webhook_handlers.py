######## GITHUB WEBHOOK HANDLERS ########
# from github import Github
import inspect
import json
import logging
import os
import socket
import time
import traceback
import uuid
from typing import Any, Dict, Union

import github
import langchain
import ray
from dotenv import load_dotenv
from github import Auth, GithubIntegration
from github.Issue import Issue
from github.PaginatedList import PaginatedList
from github.PullRequest import PullRequest
from github.IssueComment import IssueComment
from github.Repository import Repository
from github.TimelineEvent import TimelineEvent
from langchain import hub
# from langchain.tools.github.utils import generate_branch_name

# from github_agent import GH_Agent
from ai_ta_backend.agents.ml4bio_agent import WorkflowAgent
from ai_ta_backend.agents.utils import get_langsmith_trace_sharable_url

hostname = socket.gethostname()
RUNNING_ON_LOCAL = False
if 'railway' not in hostname:
  RUNNING_ON_LOCAL = True

# load API keys from globally-availabe .env file
load_dotenv(override=True)

langchain.debug = False  # True for more detailed logs

MESSAGE_HANDLE_ISSUE_OPENED = f"""Thanks for opening a new issue! I'll now try to finish this implementation and open a PR for you to review.
    
{'You can monitor the [LangSmith trace here](https://smith.langchain.com/o/f7abb6a0-31f6-400c-8bc1-62ade4b67dc1/projects/p/c2ec9de2-71b4-4042-bea0-c706b38737e2).' if 'ML4Bio' in os.environ['LANGCHAIN_PROJECT'] else ''}

Feel free to comment in this thread to give me additional instructions, or I'll tag you in a comment if I get stuck.
If I think I'm successful I'll 'request your review' on the resulting PR. Just watch for emails while I work.
"""

def handle_github_event(payload: Dict[str, Any]):
  """Main entry point for all actions that take place on Github website.

  , langsmith_run_id: uuid.UUID

  Args:
      payload (str): Union[Issue, PullRequest, IssueComment]
      langsmith_run_id (uuid.UUID): UUID to use for the Langsmith trace.

  Raises:
      ValueError: _description_
  """
  # payload: Dict[str, Any] = json.loads(gh_webhook_payload)
  langsmith_run_id = str(uuid.uuid4()) # for Langsmith 
  
  if not payload:
    raise ValueError(f"Missing the body of the webhook response. Response is {payload}")

  # API reference for webhook endpoints https://docs.github.com/en/webhooks-and-events/webhooks/webhook-events-and-payloads#issue_comment
  if payload.get('action') == 'opened' and payload.get('pull_request'):
    handle_pull_request_opened(payload, langsmith_run_id)
  elif payload.get('action') in ['opened', 'edited'] and payload.get('issue'):
    handle_issue_opened(payload, langsmith_run_id)
  elif payload.get('action') in ['created', 'edited'] and payload.get('comment'):
    handle_comment_opened(payload, langsmith_run_id)


def handle_issue_opened(payload, langsmith_run_id):
  """ This is the primary entry point to the app; Just open an issue!

  Args:
      payload (_type_): From github, see their webhook docs.
  """
  logging.warning(f'fAuth {os.environ["GITHUB_APP_ID"]}')
  logging.error(f'Auth {os.environ["GITHUB_APP_PRIVATE_KEY"]}')
  print("Auth ", os.environ["GITHUB_APP_ID"])
  print("Auth ", os.environ["GITHUB_APP_PRIVATE_KEY"])
  auth = Auth.AppAuth(
      os.environ["GITHUB_APP_ID"],
      os.environ["GITHUB_APP_PRIVATE_KEY"],
  )
  gi = GithubIntegration(auth=auth)
  installation = gi.get_installations()[0]
  g = installation.get_github_for_installation()

  print("After get instillation")
  logging.info("After get instillation")

  issue = payload['issue']
  repo_name = payload["repository"]["full_name"]
  repo: Repository = g.get_repo(repo_name)
  base_branch = repo.get_branch(payload["repository"]["default_branch"])
  number = payload.get('issue').get('number')
  issue: Issue = repo.get_issue(number=number)

  metadata = {"issue": str(issue), 'number': number, "repo_name": repo_name, "langsmith_run_id": langsmith_run_id}
  # logging.info(f"New issue created: #{number}", metadata)
  # logging.info(f"New issue created: #{number}. Metadata: {metadata}")

  # log = Log(message=f"New issue created: #{number}", metadata=metadata)
  # log_client = LogClient(os.environ['NEW_RELIC_LICENSE_KEY'])
  # response = log_client.send(log)
  # response.raise_for_status()

  try:
    result_futures = []

    # 1. INTRO COMMENT
    # issue.create_comment(messageForNewIssues)
    # result_futures.append(post_comment.remote(issue_or_pr=issue, text=MESSAGE_HANDLE_ISSUE_OPENED, time_delay_s=0))

    # 2. SHARABLE URL (in background)
    result_futures.append(post_sharable_url.remote(issue=issue, langsmith_run_id=langsmith_run_id, time_delay_s=20))

    # 3. RUN BOT
    # bot = github_agent.GH_Agent.remote()
    prompt = hub.pull("kastanday/new-github-issue").format(issue_description=format_issue(issue))
    # result_futures.append(bot.launch_gh_agent.remote(prompt, active_branch=base_branch, langsmith_run_id=langsmith_run_id))
    bot = WorkflowAgent(langsmith_run_id=langsmith_run_id)
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
    
    if RUNNING_ON_LOCAL:
      print(err_str)
    else:
      issue.create_comment(err_str)


def handle_pull_request_opened(payload: Dict[str, Any], langsmith_run_id: str):
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
    # issue.create_comment(messageForNewPRs)

    result_futures = []

    # 1. INTRO COMMENT
    # issue.create_comment(messageForNewIssues)
    result_futures.append(post_comment.remote(issue_or_pr=pr, text=messageForNewPRs, time_delay_s=0))

    # 2. SHARABLE URL (in background)
    result_futures.append(post_sharable_url.remote(issue=pr, langsmith_run_id=langsmith_run_id, time_delay_s=30))

    # 3. RUN BOT
    
    print("LAUNCHING BOT")
    bot = WorkflowAgent(langsmith_run_id=langsmith_run_id)
    # pr_description = bot.github_api_wrapper.get_pull_request(number)
    # instruction = f"Please implement these changes by creating or editing the necessary files. First read all existing comments to better understand your task. Then read the existing files to see the progress. Finally implement any and all remaining code to make the project work as the commenter intended (but no need to open a new PR, your edits are automatically committed every time you use a tool to edit files). Feel free to ask for help, or leave a comment on the PR if you're stuck. Here's the latest PR: {str(pr_description)}"
    # result = bot.launch_gh_agent(instruction, active_branch=branch_name)
    result = bot.run(comment)
    # COLLECT PARALLEL RESULTS
    for i in range(0, len(result_futures)): 
      ready, not_ready = ray.wait(result_futures)
      result = ray.get(ready[0])
      result_futures = not_ready
      if not result_futures:
        break

    # FIN: Conclusion & results comment
    ray.get(post_comment.remote(issue_or_pr=pr, text=str(result['output']), time_delay_s=0))
  except Exception as e:
    print(f"Error: {e}")
    logging.error(f"❌❌ Error in {inspect.currentframe().f_code.co_name}: {e}\nTraceback:\n", traceback.print_exc())
    err_str = f"Error in {inspect.currentframe().f_code.co_name}: {e}" + "\nTraceback\n```\n" + str(traceback.format_exc()) + "\n```"
    if RUNNING_ON_LOCAL:
      print(err_str)
    else:
      issue.create_comment(f"Bot hit a runtime exception during execution. TODO: have more bots debug this.\nError:{err_str}")



def handle_comment_opened(payload, langsmith_run_id):
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
    result_futures = []
    if is_pr:
      print("🥵🥵🥵🥵🥵🥵🥵🥵🥵🥵 COMMENT ON A PR")
      pr: PullRequest = repo.get_pull(number=number)
      branch_name = pr.head.ref
      print(f"Head branch_name: {branch_name}")
      
      # LAUNCH NEW PR COMMENT BOT 
      messageForNewPRs = "Thanks for commenting on this PR!! I'll now try to finish this implementation and I'll comment if I get blocked or (WIP) 'request your review' if I think I'm successful. So just watch for emails while I work. Please comment to give me additional instructions."
      # 1. INTRO COMMENT
      # issue.create_comment(messageForNewIssues)
      result_futures.append(post_comment.remote(issue_or_pr=pr, text=messageForNewPRs, time_delay_s=0))

      # 2. SHARABLE URL (in background)
      result_futures.append(post_sharable_url.remote(issue=pr, langsmith_run_id=langsmith_run_id, time_delay_s=30))

      # 3. RUN BOT
      bot = WorkflowAgent(langsmith_run_id=langsmith_run_id)
      instruction = f"Please complete this work-in-progress pull request (PR number {number}) by implementing the changes discussed in the comments. You can update and create files to make all necessary changes. First use read_file to read any files in the repo that seem relevant. Then, when you're ready, start implementing changes by creating and updating files. Implement any and all remaining code to make the project work as the commenter intended. You don't have to commit your changes, they are saved automaticaly on every file change. The last step is to complete the PR and leave a comment tagging the relevant humans for review, or list any concerns or final changes necessary in your comment. Feel free to ask for help, or leave a comment on the PR if you're stuck.  Here's your latest PR assignment: {format_issue(issue)}"
      result = bot.run(instruction)
      
        # COLLECT PARALLEL RESULTS
      for i in range(0, len(result_futures)): 
        ready, not_ready = ray.wait(result_futures)
        result = ray.get(ready[0])
        result_futures = not_ready
        if not result_futures:
          break

      # FIN: Conclusion & results comment
      ray.get(post_comment.remote(issue_or_pr=pr, text=str(result['output']), time_delay_s=0))
    else:
      # IS COMMENT ON ISSUE
      print("🤗🤗🤗🤗🤗🤗🤗🤗🤗🤗 THIS IS A COMMENT ON AN ISSUE")
      messageForIssues = "Thanks for opening a new or edited comment on an issue! We'll try to implement changes per your updated request, and will attempt to contribute to any existing PRs related to this or open a new PR if necessary."
      # 1. INTRO COMMENT
      # issue.create_comment(messageForNewIssues)
      result_futures.append(post_comment.remote(issue_or_pr=pr, text=messageForIssues, time_delay_s=0))

      # 2. SHARABLE URL (in background)
      result_futures.append(post_sharable_url.remote(issue=pr, langsmith_run_id=langsmith_run_id, time_delay_s=30))

      # 3. RUN BOT

      # todo: refactor with new branch name creation
      unique_branch_name = ensure_unique_branch_name(repo, "bot-branch")
      # bot = github_agent.GH_Agent()
      # issue_description = bot.github_api_wrapper.get_issue(number)
      # instruction = f"Your boss has just commented on the Github issue that was assigned to you, please review their latest comments and complete the work assigned. There may or may not be an open PR related to this already. Open or complete that PR by implementing the changes discussed in the comments. You can update and create files to make all necessary changes. First use read_file to read any files in the repo that seem relevant. Then, when you're ready, start implementing changes by creating and updating files. Implement any and all remaining code to make the project work as the commenter intended. You don't have to commit your changes, they are saved automatically on every file change. The last step is to complete the PR and leave a comment tagging the relevant humans for review, or list any concerns or final changes necessary in your comment. Feel free to ask for help, or leave a comment on the PR if you're stuck. Here's your latest PR assignment: {str(issue_description)}"
      # result = bot.launch_gh_agent(instruction, active_branch=unique_branch_name)
      bot = WorkflowAgent(langsmith_run_id=langsmith_run_id)
      result = bot.run(comment)
      # COLLECT PARALLEL RESULTS
      for i in range(0, len(result_futures)): 
        ready, not_ready = ray.wait(result_futures)
        result = ray.get(ready[0])
        result_futures = not_ready
        if not result_futures:
          break

      # FIN: Conclusion & results comment
      ray.get(post_comment.remote(issue_or_pr=pr, text=str(result['output']), time_delay_s=0))
  except Exception as e:
    logging.error(f"❌❌ Error in {inspect.currentframe().f_code.co_name}: {e}\nTraceback:\n", traceback.print_exc())    
    err_str = f"Error in {inspect.currentframe().f_code.co_name}: {e}" + "\nTraceback\n```\n" + str(traceback.format_exc()) + "\n```"
    if RUNNING_ON_LOCAL:
      print(err_str)
    else:
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
def post_sharable_url(issue, langsmith_run_id, time_delay_s):
  sharable_url = get_langsmith_trace_sharable_url(langsmith_run_id, time_delay_s=time_delay_s)
  text = f"👉 [Follow the bot's progress in real time on LangSmith]({sharable_url})."
  ray.get(post_comment.remote(issue_or_pr=issue, text=text, time_delay_s=0))


def format_issue(issue):
  linked_pr = get_linked_pr_from_issue(issue)
  title = f"Title: {issue.title}."
  existing_pr = f"Existing PR addressing issue: {linked_pr}" if linked_pr else ""
  opened_by = f"Opened by user: {issue.user.login}" if type(issue.user) == github.NamedUser.NamedUser else ''
  body = f"Body: {issue.body}"
  return "\n".join([title, opened_by, existing_pr, body])

def get_linked_pr_from_issue(issue: Issue) -> PullRequest | None:
  """Check if the given issue has a linked pull request.

  This function iterates over the timeline of the issue and checks if there is a 'cross-referenced' event.
  If such an event is found, it checks if the source of the event is an issue and if so, it returns the issue as a pull request.

  Usage: 
  issue: Issue = repo.get_issue(number=8)
  pr_or_none = check_if_issue_has_linked_pr(issue)

  Args:
      issue (Issue): The issue to check for a linked pull request.

  Returns:
      PullRequest: The linked pull request if it exists, None otherwise.
  """
  events_pages: PaginatedList[TimelineEvent] = issue.get_timeline()
  pg_num = 0
  while events_pages.get_page(pg_num):
    page = events_pages.get_page(pg_num)
    pg_num += 1
    for e in page:
      if str(e.event) == 'cross-referenced':
        if e.source and e.source.issue:
            return e.source.issue.as_pull_request()

def get_linked_issue_from_pr(pr: PullRequest) -> Issue | None:
  """Check if the given pull request has a linked issue.

  This function iterates over the timeline of the pull request and checks if there is a 'cross-referenced' event.
  If such an event is found, it checks if the source of the event is a pull request and if so, it returns the pull request as an issue.

  Usage: 
  pr: PullRequest = repo.get_pull(number=8)
  issue_or_none = check_if_pr_has_linked_issue(pr)

  Args:
      pr (PullRequest): The pull request to check for a linked issue.

  Returns:
      Issue: The linked issue if it exists, None otherwise.
  """
  events_pages: PaginatedList[TimelineEvent] = pr.as_issue().get_timeline()
  pg_num = 0
  while events_pages.get_page(pg_num):
    page = events_pages.get_page(pg_num)
    pg_num += 1
    for e in page:
      if str(e.event) == 'cross-referenced':
        if e.source and e.source.issue:
            return e.source.issue
