######## GITHUB WEBHOOK HANDLERS ########

# from github import Github
import os

from github import Auth, GithubException, GithubIntegration
from github.Issue import Issue
from github.PullRequest import PullRequest

from ai_ta_backend.agents import handle_new_pr


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
    bot = handle_new_pr.PR_Bot(branch_name=branch_name)
    bot.on_new_pr(number=number)
  except Exception as error:
    print(f"Error: {error}")
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
  repo = g.get_repo(repo_name)
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

    print("Creating branch name")
    proposed_branch_name = handle_new_pr.convert_issue_to_branch_name(issue)

    # Attempt to create the branch, appending _v{i} if the name already exists
    i = 0
    new_branch_name = proposed_branch_name
    while True:
      try:
          repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=base_branch.commit.sha)
          print(f"Branch '{new_branch_name}' created successfully!")
          break # Exit the loop when successful
      except GithubException as e:
          if e.status == 422 and "Reference already exists" in e.data['message']:
              i += 1
              new_branch_name = f"{proposed_branch_name}_v{i}"
              print(f"Branch name already exists. Trying with {new_branch_name}...")
          else:
              # Handle any other exceptions
              print(f"Failed to create branch. Error: {e}")
              break


    print("LAUNCHING BOT")
    bot = handle_new_pr.PR_Bot(new_branch_name)
    bot.on_new_issue(number=number)
  except Exception as error:
    print(f"Error: {error}")


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

      print("LAUNCHING BOT for PR comment:")
      bot = handle_new_pr.PR_Bot(branch_name=branch_name)
      final = bot.on_pr_comment(number=number)
      print("👇FINAL RESULT FROM PR COMMENT BOT 👇:\n", final)
    else:
      # IS COMMENT ON ISSUE
      print("🤗🤗🤗🤗🤗🤗🤗🤗🤗🤗 THIS IS A COMMENT ON AN ISSUE")
      messageForIssues = "Thanks for opening a new or edited comment on an issue! This bot is experimental (the PR comment bot works better), but we'll try to implement changes per your updated request."
      issue.create_comment(messageForIssues)

      print("LAUNCHING BOT for ISSUE comment:")
      bot = handle_new_pr.PR_Bot(branch_name=branch_name)
      final = bot.on_pr_comment(number=number)
      print("👇FINAL RESULT FROM PR COMMENT BOT 👇:\n", final)
  except Exception as e:
    print(f"Error: {e}")
    issue.create_comment(f"Bot hit a runtime exception during execution. TODO: have more bots debug this.\nError: {e}")
