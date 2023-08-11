import os
import re
import time
from typing import Any, List, Union

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from h11 import Response
# from qdrant_client import QdrantClient
from sqlalchemy import JSON

from ai_ta_backend.vector_database import Ingest
from ai_ta_backend.web_scrape import main_crawler, mit_course_download

app = Flask(__name__)
CORS(app)

# load API keys from globally-availabe .env file
# load_dotenv(dotenv_path='.env', override=True)
load_dotenv()


@app.route('/')
def index() -> JSON:
  """_summary_

  Args:
      test (int, optional): _description_. Defaults to 1.

  Returns:
      JSON: _description_
  """
  return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})


@app.route('/coursera', methods=['GET'])
def coursera() -> JSON:
  try:
    course_name: str = request.args.get('course_name')  # type: ignore
    coursera_course_name: str = request.args.get('coursera_course_name')  # type: ignore
  except Exception as e:
    print(f"No course name provided: {e}")

  ingester = Ingest()
  results = ingester.ingest_coursera(coursera_course_name, course_name)  # type: ignore
  response = jsonify(results)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/github', methods=['GET'])
def github() -> JSON:
  try:
    course_name: str = request.args.get('course_name')  # type: ignore
    github_url: str = request.args.get('github_url')  # type: ignore
  except Exception as e:
    print(f"No course name provided: {e}")

  print("In /github")
  ingester = Ingest()
  results = ingester.ingest_github(github_url, course_name)
  response = jsonify(results)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/delete-entire-course', methods=['GET'])
def delete_entire_course():
  try:
    course_name: str = request.args.get('course_name')  # type: ignore
    # coursera_course_name: str = request.args.get('coursera_course_name') # type: ignore
  except Exception as e:
    print(f"No course name provided: {e}")

  ingester = Ingest()
  results = ingester.delete_entire_course(course_name)  # type: ignore
  response = jsonify(results)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/getTopContexts', methods=['GET'])
def getTopContexts():
  """Get most relevant contexts for a given search query.
  
  Return value

  ## GET arguments
  course name (optional) str
      A json response with TBD fields.
  search_query
  top_n
  
  Returns
  -------
  JSON
      A json response with TBD fields.
  Metadata fileds
  * pagenumber_or_timestamp
  * readable_filename
  * s3_pdf_path
  
  Example: 
  [
    {
      'readable_filename': 'Lumetta_notes', 
      'pagenumber_or_timestamp': 'pg. 19', 
      's3_pdf_path': '/courses/<course>/Lumetta_notes.pdf', 
      'text': 'In FSM, we do this...'
    }, 
  ]

  Raises
  ------
  Exception
      Testing how exceptions are handled.
  """
  # todo: best way to handle optional arguments?
  try:
    course_name: str = request.args.get('course_name')
    search_query: str = request.args.get('search_query')
    token_limit: int = request.args.get('token_limit')
  except Exception as e:
    print("No course name provided.")

  if search_query is None:
    return jsonify({"error": "No parameter `search_query` provided. It is undefined."})
  if token_limit is None:
    token_limit = 3_000
  else:
    token_limit = int(token_limit)

  ingester = Ingest()
  found_documents = ingester.getTopContexts(search_query, course_name, token_limit)

  response = jsonify(found_documents)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/get_stuffed_prompt', methods=['GET'])
def get_stuffed_prompt():
  """Get most relevant contexts for a given search query.
  
  ## GET arguments
  course name (optional) str
      A json response with TBD fields.
  search_query
  top_n
  
  Returns
  -------
    String
    
  """
  # todo: best way to handle optional arguments?
  try:
    course_name: str = request.args.get('course_name')
    search_query: str = request.args.get('search_query')
    token_limit: int = request.args.get('token_limit')
  except Exception as e:
    print("No course name provided.")

  print("In /getTopContexts: ", search_query)
  if search_query is None:
    return jsonify({"error": "No parameter `search_query` provided. It is undefined."})
  if token_limit is None:
    token_limit = 3_000
  else:
    token_limit = int(token_limit)

  ingester = Ingest()
  prompt = ingester.get_stuffed_prompt(search_query, course_name, token_limit)

  response = jsonify(prompt)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/ingest', methods=['GET'])
def ingest():
  """Recursively ingests anything from S3 filepath and below. 
  Pass a s3_paths filepath (not URL) into our S3 bucket.
  
  Ingests all files, not just PDFs. 
  
  args:
    s3_paths: str | List[str]

  Returns:
      str: Success or Failure message. Failure message if any failures. TODO: email on failure.
  """

  print("In /ingest")

  ingester = Ingest()
  s3_paths: List[str] | str = request.args.get('s3_paths')
  course_name: List[str] | str = request.args.get('course_name')
  success_fail_dict = ingester.bulk_ingest(s3_paths, course_name)

  response = jsonify(success_fail_dict)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/getContextStuffedPrompt', methods=['GET'])
def getContextStuffedPrompt():
  """
  Get a stuffed prompt for a given user question and course name.
  Args : 
    search_query (str)
    course_name (str) : used for metadata filtering
  Returns : str
    a very long "stuffed prompt" with question + summaries of 20 most relevant documents.
  """
  print("In /getContextStuffedPrompt")

  ingester = Ingest()
  search_query: str = str(request.args.get('search_query'))  # type: ignore
  course_name: str = str(request.args.get('course_name'))  # type: ignore
  top_n: int = int(request.args.get('top_n'))  # type: ignore
  top_k_to_search: int = int(request.args.get('top_k_to_search'))  # type: ignore

  start_time = time.monotonic()
  stuffed_prompt = ingester.get_context_stuffed_prompt(search_query, course_name, top_n, top_k_to_search)
  print(f"⏰ Runtime of EXTREME prompt stuffing: {(time.monotonic() - start_time):.2f} seconds")
  response = jsonify({"prompt": stuffed_prompt})

  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/getAll', methods=['GET'])
def getAll():
  """Get all course materials based on the course_name
  """

  print("In /getAll")

  ingester = Ingest()
  course_name: List[str] | str = request.args.get('course_name')
  distinct_dicts = ingester.getAll(course_name)
  response = jsonify({"all_s3_paths": distinct_dicts})

  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


#Write api to delete s3 files for a course
@app.route('/delete', methods=['DELETE'])
def delete():
  """Delete all course materials based on the course_name
    """

  print("In /delete")

  ingester = Ingest()
  course_name: List[str] | str = request.args.get('course_name')
  s3_path: str = request.args.get('s3_path')
  success_or_failure = ingester.delete_data(s3_path, course_name)
  response = jsonify({"outcome": success_or_failure})

  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/log', methods=['GET'])
def log():
  """
  todo
  """

  print("In /log")

  ingester = Ingest()
  # course_name: List[str] | str = request.args.get('course_name')
  success_or_failure = ingester.log_to_arize('course_name', 'test', 'completion')
  response = jsonify({"outcome": success_or_failure})

  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/web-scrape', methods=['GET'])
def scrape():
  url: str = request.args.get('url')
  max_urls: int = request.args.get('max_urls')
  max_depth: int = request.args.get('max_depth')
  timeout: int = request.args.get('timeout')
  course_name: str = request.args.get('course_name')
  base_url_bool: str = request.args.get('base_url_on')

  # print all input params
  print(f"Web scrape!")
  print(f"Url: {url}")
  print(f"Max Urls: {max_urls}")
  print(f"Max Depth: {max_depth}")
  print(f"Timeout in Seconds ⏰: {timeout}")

  success_fail_dict = main_crawler(url, course_name, max_urls, max_depth, timeout, base_url_bool)

  response = jsonify(success_fail_dict)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


@app.route('/mit-download', methods=['GET'])
def mit_download_course():
  url: str = request.args.get('url')
  course_name: str = request.args.get('course_name')
  local_dir: str = request.args.get('local_dir')

  success_fail = mit_course_download(url, course_name, local_dir)

  response = jsonify(success_fail)
  response.headers.add('Access-Control-Allow-Origin', '*')
  return response


# TODO: add a way to delete items from course based on base_url

from github import Github


# TODO: handle new comment on PR. Make sure task queue is not overrun.
# IN PROGRESS: Github agent webhooks
def handle_pull_request_opened(payload):
  print("RIGHT BEFORE GITHUB INSTANCE")
  print("os.getenv(GITHUB_APP_ID)", os.getenv("GITHUB_APP_ID"))
  print("os.getenv(GITHUB_APP_PRIVATE_KEY)", os.getenv("GITHUB_APP_PRIVATE_KEY"))
  g = Github(os.getenv("GITHUB_APP_ID"), os.getenv("GITHUB_APP_PRIVATE_KEY"))

  messageForNewPRs = "Thanks for opening a new PR! Please follow our contributing guidelines to make your PR easier to review."
  print(f"Received a pull request event for #{payload['number']}")
  try:
    repo = g.get_repo(payload["pull_request"]["head"]["repo"]["full_name"])
    issue = repo.get_issue(number=payload['number'])
    issue.create_comment(messageForNewPRs)
  except Exception as error:
    print(f"Error: {error}")


# IN PROGRESS: Github App Webhooks (for lil-jr-dev)
@app.route('/api/webhook', methods=['POST'])
def webhook():
  print("In api/webhook! YAYYY")
  payload = request.json
  print(f"In api/webhook! Payload: {payload}")
  # {'action': 'opened', 'number': 9, 'pull_request': {'url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/pulls/9';, 'id': 1471186429, 'node_id': 'PR_kwDOJ2JgD85XsIX9', 'html_url': 'https://github.com/KastanDay/smol-dev-webscrape/pull/9';, 'diff_url': 'https://github.com/KastanDay/smol-dev-webscrape/pull/9.diff';, 'patch_url': 'https://github.com/KastanDay/smol-dev-webscrape/pull/9.patch';, 'issue_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/issues/9';, 'number': 9, 'state': 'open', 'locked': False, 'title': 'New pr 2', 'user': {'login': 'KastanDay', 'id': 13607221, 'node_id': 'MDQ6VXNlcjEzNjA3MjIx', 'avatar_url': 'https://avatars.githubusercontent.com/u/13607221?v=4';, 'gravatar_id': '', 'url': 'https://api.github.com/users/KastanDay';, 'html_url': 'https://github.com/KastanDay';, 'followers_url': 'https://api.github.com/users/KastanDay/followers';, 'following_url': 'https://api.github.com/users/KastanDay/following{/other_user}', 'gists_url': 'https://api.github.com/users/KastanDay/gists{/gist_id}', 'starred_url': 'https://api.github.com/users/KastanDay/starred{/owner}{/repo}', 'subscriptions_url': 'https://api.github.com/users/KastanDay/subscriptions';, 'organizations_url': 'https://api.github.com/users/KastanDay/orgs';, 'repos_url': 'https://api.github.com/users/KastanDay/repos';, 'events_url': 'https://api.github.com/users/KastanDay/events{/privacy}', 'received_events_url': 'https://api.github.com/users/KastanDay/received_events';, 'type': 'User', 'site_admin': False}, 'body': None, 'created_at': '2023-08-11T03:00:11Z', 'updated_at': '2023-08-11T03:00:11Z', 'closed_at': None, 'merged_at': None, 'merge_commit_sha': None, 'assignee': None, 'assignees': [], 'requested_reviewers': [], 'requested_teams': [], 'labels': [], 'milestone': None, 'draft': False, 'commits_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/pulls/9/commits';, 'review_comments_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/pulls/9/comments';, 'review_comment_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/pulls/comments{/number}', 'comments_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/issues/9/comments';, 'statuses_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/statuses/cd84056d3ab89867962a19407a301f648a047f53';, 'head': {'label': 'KastanDay:new_pr_2', 'ref': 'new_pr_2', 'sha': 'cd84056d3ab89867962a19407a301f648a047f53', 'user': {'login': 'KastanDay', 'id': 13607221, 'node_id': 'MDQ6VXNlcjEzNjA3MjIx', 'avatar_url': 'https://avatars.githubusercontent.com/u/13607221?v=4';, 'gravatar_id': '', 'url': 'https://api.github.com/users/KastanDay';, 'html_url': 'https://github.com/KastanDay';, 'followers_url': 'https://api.github.com/users/KastanDay/followers';, 'following_url': 'https://api.github.com/users/KastanDay/following{/other_user}', 'gists_url': 'https://api.github.com/users/KastanDay/gists{/gist_id}', 'starred_url': 'https://api.github.com/users/KastanDay/starred{/owner}{/repo}', 'subscriptions_url': 'https://api.github.com/users/KastanDay/subscriptions';, 'organizations_url': 'https://api.github.com/users/KastanDay/orgs';, 'repos_url': 'https://api.github.com/users/KastanDay/repos';, 'events_url': 'https://api.github.com/users/KastanDay/events{/privacy}', 'received_events_url': 'https://api.github.com/users/KastanDay/received_events';, 'type': 'User', 'site_admin': False}, 'repo': {'id': 660758543, 'node_id': 'R_kgDOJ2JgDw', 'name': 'smol-dev-webscrape', 'full_name': 'KastanDay/smol-dev-webscrape', 'private': False, 'owner': {'login': 'KastanDay', 'id': 13607221, 'node_id': 'MDQ6VXNlcjEzNjA3MjIx', 'avatar_url': 'https://avatars.githubusercontent.com/u/13607221?v=4';, 'gravatar_id': '', 'url': 'https://api.github.com/users/KastanDay';, 'html_url': 'https://github.com/KastanDay';, 'followers_url': 'https://api.github.com/users/KastanDay/followers';, 'following_url': 'https://api.github.com/users/KastanDay/following{/other_user}', 'gists_url': 'https://api.github.com/users/KastanDay/gists{/gist_id}', 'starred_url': 'https://api.github.com/users/KastanDay/starred{/owner}{/repo}', 'subscriptions_url': 'https://api.github.com/users/KastanDay/subscriptions';, 'organizations_url': 'https://api.github.com/users/KastanDay/orgs';, 'repos_url': 'https://api.github.com/users/KastanDay/repos';, 'events_url': 'https://api.github.com/users/KastanDay/events{/privacy}', 'received_events_url': 'https://api.github.com/users/KastanDay/received_events';, 'type': 'User', 'site_admin': False}, 'html_url': 'https://github.com/KastanDay/smol-dev-webscrape';, 'description': None, 'fork': False, 'url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape';, 'forks_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/forks';, 'keys_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/keys{/key_id}', 'collaborators_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/collaborators{/collaborator}', 'teams_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/teams';, 'hooks_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/hooks';, 'issue_events_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/issues/events{/number}', 'events_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/events';, 'assignees_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/assignees{/user}', 'branches_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/branches{/branch}', 'tags_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/tags';, 'blobs_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/git/blobs{/sha}', 'git_tags_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/git/tags{/sha}', 'git_refs_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/git/refs{/sha}', 'trees_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/git/trees{/sha}', 'statuses_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/statuses/{sha}', 'languages_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/languages';, 'stargazers_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/stargazers';, 'contributors_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/contributors';, 'subscribers_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/subscribers';, 'subscription_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/subscription';, 'commits_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/commits{/sha}', 'git_commits_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/git/commits{/sha}', 'comments_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/comments{/number}', 'issue_comment_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/issues/comments{/number}', 'contents_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/contents/{+path}', 'compare_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/compare/{base}...{head}', 'merges_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/merges';, 'archive_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/{archive_format}{/ref}', 'downloads_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/downloads';, 'issues_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/issues{/number}', 'pulls_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/pulls{/number}', 'milestones_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/milestones{/number}', 'notifications_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/notifications{?since,all,participating}', 'labels_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/labels{/name}', 'releases_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/releases{/id}', 'deployments_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/deployments';, 'created_at': '2023-06-30T19:14:48Z', 'updated_at': '2023-08-11T01:25:42Z', 'pushed_at': '2023-08-11T03:00:11Z', 'git_url': 'git://github.com/KastanDay/smol-dev-webscrape.git', 'ssh_url': 'git@github.com:KastanDay/smol-dev-webscrape.git', 'clone_url': 'https://github.com/KastanDay/smol-dev-webscrape.git';, 'svn_url': 'https://github.com/KastanDay/smol-dev-webscrape';, 'homepage': None, 'size': 11, 'stargazers_count': 0, 'watchers_count': 0, 'language': 'C', 'has_issues': True, 'has_projects': True, 'has_downloads': True, 'has_wiki': True, 'has_pages': False, 'has_discussions': False, 'forks_count': 0, 'mirror_url': None, 'archived': False, 'disabled': False, 'open_issues_count': 6, 'license': None, 'allow_forking': True, 'is_template': False, 'web_commit_signoff_required': False, 'topics': [], 'visibility': 'public', 'forks': 0, 'open_issues': 6, 'watchers': 0, 'default_branch': 'main', 'allow_squash_merge': True, 'allow_merge_commit': True, 'allow_rebase_merge': True, 'allow_auto_merge': False, 'delete_branch_on_merge': False, 'allow_update_branch': False, 'use_squash_pr_title_as_default': False, 'squash_merge_commit_message': 'COMMIT_MESSAGES', 'squash_merge_commit_title': 'COMMIT_OR_PR_TITLE', 'merge_commit_message': 'PR_TITLE', 'merge_commit_title': 'MERGE_MESSAGE'}}, 'base': {'label': 'KastanDay:main', 'ref': 'main', 'sha': 'f31256e7406eebbabe24bd5dd99cbb54bc811783', 'user': {'login': 'KastanDay', 'id': 13607221, 'node_id': 'MDQ6VXNlcjEzNjA3MjIx', 'avatar_url': 'https://avatars.githubusercontent.com/u/13607221?v=4';, 'gravatar_id': '', 'url': 'https://api.github.com/users/KastanDay';, 'html_url': 'https://github.com/KastanDay';, 'followers_url': 'https://api.github.com/users/KastanDay/followers';, 'following_url': 'https://api.github.com/users/KastanDay/following{/other_user}', 'gists_url': 'https://api.github.com/users/KastanDay/gists{/gist_id}', 'starred_url': 'https://api.github.com/users/KastanDay/starred{/owner}{/repo}', 'subscriptions_url': 'https://api.github.com/users/KastanDay/subscriptions';, 'organizations_url': 'https://api.github.com/users/KastanDay/orgs';, 'repos_url': 'https://api.github.com/users/KastanDay/repos';, 'events_url': 'https://api.github.com/users/KastanDay/events{/privacy}', 'received_events_url': 'https://api.github.com/users/KastanDay/received_events';, 'type': 'User', 'site_admin': False}, 'repo': {'id': 660758543, 'node_id': 'R_kgDOJ2JgDw', 'name': 'smol-dev-webscrape', 'full_name': 'KastanDay/smol-dev-webscrape', 'private': False, 'owner': {'login': 'KastanDay', 'id': 13607221, 'node_id': 'MDQ6VXNlcjEzNjA3MjIx', 'avatar_url': 'https://avatars.githubusercontent.com/u/13607221?v=4';, 'gravatar_id': '', 'url': 'https://api.github.com/users/KastanDay';, 'html_url': 'https://github.com/KastanDay';, 'followers_url': 'https://api.github.com/users/KastanDay/followers';, 'following_url': 'https://api.github.com/users/KastanDay/following{/other_user}', 'gists_url': 'https://api.github.com/users/KastanDay/gists{/gist_id}', 'starred_url': 'https://api.github.com/users/KastanDay/starred{/owner}{/repo}', 'subscriptions_url': 'https://api.github.com/users/KastanDay/subscriptions';, 'organizations_url': 'https://api.github.com/users/KastanDay/orgs';, 'repos_url': 'https://api.github.com/users/KastanDay/repos';, 'events_url': 'https://api.github.com/users/KastanDay/events{/privacy}', 'received_events_url': 'https://api.github.com/users/KastanDay/received_events';, 'type': 'User', 'site_admin': False}, 'html_url': 'https://github.com/KastanDay/smol-dev-webscrape';, 'description': None, 'fork': False, 'url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape';, 'forks_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/forks';, 'keys_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/keys{/key_id}', 'collaborators_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/collaborators{/collaborator}', 'teams_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/teams';, 'hooks_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/hooks';, 'issue_events_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/issues/events{/number}', 'events_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/events';, 'assignees_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/assignees{/user}', 'branches_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/branches{/branch}', 'tags_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/tags';, 'blobs_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/git/blobs{/sha}', 'git_tags_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/git/tags{/sha}', 'git_refs_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/git/refs{/sha}', 'trees_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/git/trees{/sha}', 'statuses_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/statuses/{sha}', 'languages_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/languages';, 'stargazers_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/stargazers';, 'contributors_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/contributors';, 'subscribers_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/subscribers';, 'subscription_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/subscription';, 'commits_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/commits{/sha}', 'git_commits_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/git/commits{/sha}', 'comments_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/comments{/number}', 'issue_comment_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/issues/comments{/number}', 'contents_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/contents/{+path}', 'compare_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/compare/{base}...{head}', 'merges_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/merges';, 'archive_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/{archive_format}{/ref}', 'downloads_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/downloads';, 'issues_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/issues{/number}', 'pulls_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/pulls{/number}', 'milestones_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/milestones{/number}', 'notifications_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/notifications{?since,all,participating}', 'labels_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/labels{/name}', 'releases_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/releases{/id}', 'deployments_url': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/deployments';, 'created_at': '2023-06-30T19:14:48Z', 'updated_at': '2023-08-11T01:25:42Z', 'pushed_at': '2023-08-11T03:00:11Z', 'git_url': 'git://github.com/KastanDay/smol-dev-webscrape.git', 'ssh_url': 'git@github.com:KastanDay/smol-dev-webscrape.git', 'clone_url': 'https://github.com/KastanDay/smol-dev-webscrape.git';, 'svn_url': 'https://github.com/KastanDay/smol-dev-webscrape';, 'homepage': None, 'size': 11, 'stargazers_count': 0, 'watchers_count': 0, 'language': 'C', 'has_issues': True, 'has_projects': True, 'has_downloads': True, 'has_wiki': True, 'has_pages': False, 'has_discussions': False, 'forks_count': 0, 'mirror_url': None, 'archived': False, 'disabled': False, 'open_issues_count': 6, 'license': None, 'allow_forking': True, 'is_template': False, 'web_commit_signoff_required': False, 'topics': [], 'visibility': 'public', 'forks': 0, 'open_issues': 6, 'watchers': 0, 'default_branch': 'main', 'allow_squash_merge': True, 'allow_merge_commit': True, 'allow_rebase_merge': True, 'allow_auto_merge': False, 'delete_branch_on_merge': False, 'allow_update_branch': False, 'use_squash_pr_title_as_default': False, 'squash_merge_commit_message': 'COMMIT_MESSAGES', 'squash_merge_commit_title': 'COMMIT_OR_PR_TITLE', 'merge_commit_message': 'PR_TITLE', 'merge_commit_title': 'MERGE_MESSAGE'}}, '_links': {'self': {'href': 'https://api.github.com/repos/KastanDay/smol-dev-webscrape/pull

  if payload and payload['action'] == 'opened' and payload['pull_request']:
    handle_pull_request_opened(payload['pull_request'])
  return '', 200


if __name__ == '__main__':
  app.run(debug=True, port=os.getenv("PORT", default=8000))
