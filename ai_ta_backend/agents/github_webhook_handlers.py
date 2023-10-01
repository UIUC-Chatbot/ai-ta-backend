######## GITHUB WEBHOOK HANDLERS ########

# from github import Github
import os
from dis import Instruction

from github import Auth, GithubIntegration
from github.Issue import Issue
from github.PullRequest import PullRequest
from github.Repository import Repository

from ai_ta_backend.agents import github_agent


def handle_pull_request_opened(payload):
  auth = Auth.AppAuth(
      os.environ["GITHUB_APP_ID"],
      os.environ["GITHUB_APP_PRIVATE_KEY"],
  )
  gi = GithubIntegration(auth=auth)
  installation = gi.get_installations()[0]
  g = installation.get_github_for_installation()

  repo_name = payload["repository"]["full_name"]
  repo = g.get_repo(repo_name)

  number = payload.get('issue').get('number') # AttributeError: 'NoneType' object has no attribute 'get'
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
    bot = github_agent.GH_Agent(branch_name=branch_name)
    pr_description = bot.github_api_wrapper.get_pull_request(number)
    instruction = f"Please implement these changes by creating or editing the necessary files. First read all existing comments to better understand your task. Then read the existing files to see the progress. Finally implement any and all remaining code to make the project work as the commenter intended (but no need to open a new PR, your edits are automatically committed every time you use a tool to edit files). Feel free to ask for help, or leave a comment on the PR if you're stuck. Here's the latest PR: {str(pr_description)}"
    result = bot.launch_gh_agent(instruction, active_branch=branch_name)
    issue.create_comment(result)
  except Exception as e:
    print(f"Error: {e}")
    issue.create_comment(f"Bot hit a runtime exception during execution. TODO: have more bots debug this.\nError:{e}")


def handle_issue_opened(payload):
  auth = Auth.AppAuth(
      os.environ["GITHUB_APP_ID"],
      os.environ["GITHUB_APP_PRIVATE_KEY"],
  )
  gi = GithubIntegration(auth=auth)
  installation = gi.get_installations()[0]
  g = installation.get_github_for_installation()

  # comment = payload['comment']
  issue = payload['issue']
  repo_name = payload["repository"]["full_name"]
  repo: Repository = g.get_repo(repo_name)
  base_branch = repo.get_branch(payload["repository"]["default_branch"])
  number = payload.get('issue').get('number')
  issue: Issue = repo.get_issue(number=number)
  
  # TODO:     comment_author = comment['user']['login'] TypeError: 'NoneType' object is not subscriptable
  comment = payload.get('comment')
  if comment:
    # not always have a comment.
    comment_author = comment['user']['login']
    comment_made_by_bot = True if comment.get('performed_via_github_app') else False
  

  print(f"New issue created: #{number}")
  try:
    messageForNewIssues = "Thanks for opening a new issue! I'll now try to finish this implementation and open a PR for you to review. I'll comment if I get blocked or 'request your review' if I think I'm successful. So just watch for emails while I work. Please comment to give me additional instructions."
    issue.create_comment(messageForNewIssues)

    unique_branch_name = 'main'
    # print("Creating branch name")
    # unique_branch_name = github_agent.generate_branch_name(issue)
    #  = ensure_unique_branch_name(repo, proposed_branch_name)

    print("LAUNCHING BOT")
    bot = github_agent.GH_Agent(branch_name=unique_branch_name)
    issue_description = bot.github_api_wrapper.get_issue(number)
    instruction = f"Please implement these changes by creating or editing the necessary files. First use read_file to read any files in the repo that seem relevant. Then, when you're ready, start implementing changes by creating and updating files. Implement any and all remaining code to make the project work as the commenter intended. The last step is to create a PR with a clear and concise title and description, list any concerns or final changes necessary in the PR body. Feel free to ask for help, or leave a comment on the PR if you're stuck.  Here's your latest assignment: {str(issue_description)}"
    result = bot.launch_gh_agent(instruction, active_branch=unique_branch_name)
    issue.create_comment(result)
  except Exception as e:
    print(f"Error: {e}")
    issue.create_comment(f"{e}")


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
      issue_description = bot.github_api_wrapper.get_issue(number)
      instruction = f"Please complete this work-in-progress pull request (PR number {number}) by implementing the changes discussed in the comments. You can update and create files to make all necessary changes. First use read_file to read any files in the repo that seem relevant. Then, when you're ready, start implementing changes by creating and updating files. Implement any and all remaining code to make the project work as the commenter intended. You don't have to commit your changes, they are saved automaticaly on every file change. The last step is to complete the PR and leave a comment tagging the relevant humans for review, or list any concerns or final changes necessary in your comment. Feel free to ask for help, or leave a comment on the PR if you're stuck.  Here's your latest PR assignment: {str(issue_description)}"
      result = bot.launch_gh_agent(instruction, active_branch=branch_name)
      issue.create_comment(result)
    else:
      # IS COMMENT ON ISSUE
      print("🤗🤗🤗🤗🤗🤗🤗🤗🤗🤗 THIS IS A COMMENT ON AN ISSUE")
      messageForIssues = "Thanks for opening a new or edited comment on an issue! We'll try to implement changes per your updated request, and will attempt to contribute to any existing PRs related to this or open a new PR if necessary."
      issue.create_comment(messageForIssues)

      unique_branch_name = ensure_unique_branch_name(repo, "bot-branch")
      bot = github_agent.GH_Agent()
      issue_description = bot.github_api_wrapper.get_issue(number)
      instruction = f"Your boss has just commented on the Github issue that was assigned to you, please review their latest comments and complete the work assigned. There may or may not be an open PR related to this already. Open or complete that PR by implementing the changes discussed in the comments. You can update and create files to make all necessary changes. First use read_file to read any files in the repo that seem relevant. Then, when you're ready, start implementing changes by creating and updating files. Implement any and all remaining code to make the project work as the commenter intended. You don't have to commit your changes, they are saved automatically on every file change. The last step is to complete the PR and leave a comment tagging the relevant humans for review, or list any concerns or final changes necessary in your comment. Feel free to ask for help, or leave a comment on the PR if you're stuck. Here's your latest PR assignment: {str(issue_description)}"
      result = bot.launch_gh_agent(instruction, active_branch=unique_branch_name)
      issue.create_comment(result)
  except Exception as e:
    print(f"Error: {e}")
    issue.create_comment(f"Bot hit a runtime exception during execution. TODO: have more bots debug this.\nError: {e}")

