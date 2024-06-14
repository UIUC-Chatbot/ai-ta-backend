import asyncio
import json
import time
from typing import List

from dotenv import load_dotenv
from flask import Flask
from flask import jsonify
from flask import request
from flask_cors import CORS
import ray
# from qdrant_client import QdrantClient
from sqlalchemy import JSON

from ai_ta_backend.agents.github_webhook_handlers import handle_github_event
from ai_ta_backend.vector_database import Ingest
from ai_ta_backend.web_scrape import main_crawler
from ai_ta_backend.web_scrape import mit_course_download

app = Flask(__name__)
CORS(app)

# load API keys from globally-availabe .env file
load_dotenv(dotenv_path='.env', override=True)

ray.init()

# @app.route('/')
# def index() -> JSON:
#   """_summary_

#   Args:
#       test (int, optional): _description_. Defaults to 1.

#   Returns:
#       JSON: _description_
#   """
#   return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})


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
  except Exception:
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
  except Exception:
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
  print("Web scrape!")
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


@app.route('/', methods=['POST'])  # RUN: $ smee -u https://smee.io/nRnJDGnCbWYUaSGg --port 8000
# @app.route('/api/webhook', methods=['POST']) # https://flask-ai-ta-backend-pr-34.up.railway.app/api/webhook
async def webhook():
  """
  IN PROGRESS: Github App Webhooks (for lil-jr-dev)
  Wehbook URL to use on my github app (if this route is `/api/webhook`): https://flask-ai-ta-backend-pr-34.up.railway.app/api/webhook

  DOCS: 
  API reference for Webhook objects: https://docs.github.com/en/webhooks-and-events/webhooks/webhook-events-and-payloads#issue_comment
  WEBHOOK explainer: https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/using-webhooks-with-github-apps
  """

  payload = request.json
  print("Payload received...")
  # print(payload)

  # FOR LOCAL TESTING, USE THIS PAYLOAD:
  # payload = {'action': 'created', 'issue': {'url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/issues/6';, 'repository_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2';, 'labels_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/issues/6/labels{/name}', 'comments_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/issues/6/comments';, 'events_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/issues/6/events';, 'html_url': 'https://github.com/KastanDay/ML4Bio-v2/issues/6';, 'id': 2353966410, 'node_id': 'I_kwDOLWrGSc6MTq1K', 'number': 6, 'title': "Implement an RNA-Sequence Analysis Workflow using DESEQ2. Open a new pull request on a separate branch and comment the PR number here when you're done", 'user': {'login': 'KastanDay', 'id': 13607221, 'node_id': 'MDQ6VXNlcjEzNjA3MjIx', 'avatar_url': 'https://avatars.githubusercontent.com/u/13607221?v=4';, 'gravatar_id': '', 'url': 'https://api.github.com/users/KastanDay';, 'html_url': 'https://github.com/KastanDay';, 'followers_url': 'https://api.github.com/users/KastanDay/followers';, 'following_url': 'https://api.github.com/users/KastanDay/following{/other_user}', 'gists_url': 'https://api.github.com/users/KastanDay/gists{/gist_id}', 'starred_url': 'https://api.github.com/users/KastanDay/starred{/owner}{/repo}', 'subscriptions_url': 'https://api.github.com/users/KastanDay/subscriptions';, 'organizations_url': 'https://api.github.com/users/KastanDay/orgs';, 'repos_url': 'https://api.github.com/users/KastanDay/repos';, 'events_url': 'https://api.github.com/users/KastanDay/events{/privacy}', 'received_events_url': 'https://api.github.com/users/KastanDay/received_events';, 'type': 'User', 'site_admin': False}, 'labels': [], 'state': 'open', 'locked': False, 'assignee': None, 'assignees': [], 'milestone': None, 'comments': 3, 'created_at': '2024-06-14T19:33:24Z', 'updated_at': '2024-06-14T19:49:28Z', 'closed_at': None, 'author_association': 'OWNER', 'active_lock_reason': None, 'body': 'Implement RNA-Sequence Analysis Workflow as per the following steps.\r\n\r\nAnalyze count data using DESEQ2\r\nPlease write and execute the code to do DESEQ2 analysis on the data. If you generate results, please push them to github and mention that in your pull request.\r\nMake sure you execute the code, and if it fails keep re-trying with improvements until you get something useful to share.', 'reactions': {'url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/issues/6/reactions';, 'total_count': 0, '+1': 0, '-1': 0, 'laugh': 0, 'hooray': 0, 'confused': 0, 'heart': 0, 'rocket': 0, 'eyes': 0}, 'timeline_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/issues/6/timeline';, 'performed_via_github_app': None, 'state_reason': None}, 'comment': {'url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/issues/comments/2168662835';, 'html_url': 'https://github.com/KastanDay/ML4Bio-v2/issues/6#issuecomment-2168662835';, 'issue_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/issues/6';, 'id': 2168662835, 'node_id': 'IC_kwDOLWrGSc6BQysz', 'user': {'login': 'lil-jr-dev[bot]', 'id': 141794476, 'node_id': 'BOT_kgDOCHOcrA', 'avatar_url': 'https://avatars.githubusercontent.com/in/373429?v=4';, 'gravatar_id': '', 'url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D';, 'html_url': 'https://github.com/apps/lil-jr-dev';, 'followers_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/followers';, 'following_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/following{/other_user}', 'gists_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/gists{/gist_id}', 'starred_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/starred{/owner}{/repo}', 'subscriptions_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/subscriptions';, 'organizations_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/orgs';, 'repos_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/repos';, 'events_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/events{/privacy}', 'received_events_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/received_events';, 'type': 'Bot', 'site_admin': False}, 'created_at': '2024-06-14T19:49:26Z', 'updated_at': '2024-06-14T19:49:26Z', 'author_association': 'NONE', 'body': 'Error in handle_issue_opened: 1 validation error for AzureChatOpenAI\n__root__\n  As of openai>=1.0.0, Azure endpoints should be specified via the `azure_endpoint` param not `openai_api_base` (or alias `base_url`). (type=value_error)\nTraceback\n```\nTraceback (most recent call last):\n  File "/app/ai_ta_backend/agents/github_webhook_handlers.py", line 168, in handle_issue_opened\n    bot = WorkflowAgent(langsmith_run_id=langsmith_run_id)\n  File "/app/ai_ta_backend/agents/langgraph_agent_v2.py", line 70, in __init__\n    self.llm = get_llm()\n  File "/app/ai_ta_backend/agents/langgraph_agent_v2.py", line 51, in get_llm\n    return AzureChatOpenAI(\n  File "/opt/venv/lib/python3.10/site-packages/langchain_core/load/serializable.py", line 107, in __init__\n    super().__init__(**kwargs)\n  File "pydantic/main.py", line 341, in pydantic.main.BaseModel.__init__\npydantic.error_wrappers.ValidationError: 1 validation error for AzureChatOpenAI\n__root__\n  As of openai>=1.0.0, Azure endpoints should be specified via the `azure_endpoint` param not `openai_api_base` (or alias `base_url`). (type=value_error)\n\n```', 'reactions': {'url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/issues/comments/2168662835/reactions';, 'total_count': 0, '+1': 0, '-1': 0, 'laugh': 0, 'hooray': 0, 'confused': 0, 'heart': 0, 'rocket': 0, 'eyes': 0}, 'performed_via_github_app': {'id': 373429, 'slug': 'lil-jr-dev', 'node_id': 'A_kwDOAM-hNc4ABbK1', 'owner': {'login': 'KastanDay', 'id': 13607221, 'node_id': 'MDQ6VXNlcjEzNjA3MjIx', 'avatar_url': 'https://avatars.githubusercontent.com/u/13607221?v=4';, 'gravatar_id': '', 'url': 'https://api.github.com/users/KastanDay';, 'html_url': 'https://github.com/KastanDay';, 'followers_url': 'https://api.github.com/users/KastanDay/followers';, 'following_url': 'https://api.github.com/users/KastanDay/following{/other_user}', 'gists_url': 'https://api.github.com/users/KastanDay/gists{/gist_id}', 'starred_url': 'https://api.github.com/users/KastanDay/starred{/owner}{/repo}', 'subscriptions_url': 'https://api.github.com/users/KastanDay/subscriptions';, 'organizations_url': 'https://api.github.com/users/KastanDay/orgs';, 'repos_url': 'https://api.github.com/users/KastanDay/repos';, 'events_url': 'https://api.github.com/users/KastanDay/events{/privacy}', 'received_events_url': 'https://api.github.com/users/KastanDay/received_events';, 'type': 'User', 'site_admin': False}, 'name': 'lil jr. dev', 'description': 'This will be your AI Remote Software Engineer.', 'external_url': 'https://www.uiuc.chat/';, 'html_url': 'https://github.com/apps/lil-jr-dev';, 'created_at': '2023-08-09T01:56:21Z', 'updated_at': '2023-10-11T22:08:08Z', 'permissions': {'contents': 'write', 'issues': 'write', 'metadata': 'read', 'pull_requests': 'write', 'single_file': 'write', 'statuses': 'write'}, 'events': ['issues', 'issue_comment', 'pull_request', 'pull_request_review', 'pull_request_review_comment', 'push']}}, 'repository': {'id': 761972297, 'node_id': 'R_kgDOLWrGSQ', 'name': 'ML4Bio-v2', 'full_name': 'KastanDay/ML4Bio-v2', 'private': False, 'owner': {'login': 'KastanDay', 'id': 13607221, 'node_id': 'MDQ6VXNlcjEzNjA3MjIx', 'avatar_url': 'https://avatars.githubusercontent.com/u/13607221?v=4';, 'gravatar_id': '', 'url': 'https://api.github.com/users/KastanDay';, 'html_url': 'https://github.com/KastanDay';, 'followers_url': 'https://api.github.com/users/KastanDay/followers';, 'following_url': 'https://api.github.com/users/KastanDay/following{/other_user}', 'gists_url': 'https://api.github.com/users/KastanDay/gists{/gist_id}', 'starred_url': 'https://api.github.com/users/KastanDay/starred{/owner}{/repo}', 'subscriptions_url': 'https://api.github.com/users/KastanDay/subscriptions';, 'organizations_url': 'https://api.github.com/users/KastanDay/orgs';, 'repos_url': 'https://api.github.com/users/KastanDay/repos';, 'events_url': 'https://api.github.com/users/KastanDay/events{/privacy}', 'received_events_url': 'https://api.github.com/users/KastanDay/received_events';, 'type': 'User', 'site_admin': False}, 'html_url': 'https://github.com/KastanDay/ML4Bio-v2';, 'description': 'LLMs to execute Bioinformatics workflows, esp. RNA-seq', 'fork': False, 'url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2';, 'forks_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/forks';, 'keys_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/keys{/key_id}', 'collaborators_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/collaborators{/collaborator}', 'teams_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/teams';, 'hooks_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/hooks';, 'issue_events_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/issues/events{/number}', 'events_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/events';, 'assignees_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/assignees{/user}', 'branches_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/branches{/branch}', 'tags_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/tags';, 'blobs_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/git/blobs{/sha}', 'git_tags_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/git/tags{/sha}', 'git_refs_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/git/refs{/sha}', 'trees_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/git/trees{/sha}', 'statuses_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/statuses/{sha}', 'languages_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/languages';, 'stargazers_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/stargazers';, 'contributors_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/contributors';, 'subscribers_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/subscribers';, 'subscription_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/subscription';, 'commits_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/commits{/sha}', 'git_commits_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/git/commits{/sha}', 'comments_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/comments{/number}', 'issue_comment_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/issues/comments{/number}', 'contents_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/contents/{+path}', 'compare_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/compare/{base}...{head}', 'merges_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/merges';, 'archive_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/{archive_format}{/ref}', 'downloads_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/downloads';, 'issues_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/issues{/number}', 'pulls_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/pulls{/number}', 'milestones_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/milestones{/number}', 'notifications_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/notifications{?since,all,participating}', 'labels_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/labels{/name}', 'releases_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/releases{/id}', 'deployments_url': 'https://api.github.com/repos/KastanDay/ML4Bio-v2/deployments';, 'created_at': '2024-02-22T20:46:40Z', 'updated_at': '2024-06-14T18:51:48Z', 'pushed_at': '2024-06-14T18:51:45Z', 'git_url': 'git://github.com/KastanDay/ML4Bio-v2.git', 'ssh_url': 'git@github.com:KastanDay/ML4Bio-v2.git', 'clone_url': 'https://github.com/KastanDay/ML4Bio-v2.git';, 'svn_url': 'https://github.com/KastanDay/ML4Bio-v2';, 'homepage': None, 'size': 23548, 'stargazers_count': 0, 'watchers_count': 0, 'language': 'HTML', 'has_issues': True, 'has_projects': True, 'has_downloads': True, 'has_wiki': True, 'has_pages': False, 'has_discussions': False, 'forks_count': 0, 'mirror_url': None, 'archived': False, 'disabled': False, 'open_issues_count': 5, 'license': {'key': 'mit', 'name': 'MIT License', 'spdx_id': 'MIT', 'url': 'https://api.github.com/licenses/mit';, 'node_id': 'MDc6TGljZW5zZTEz'}, 'allow_forking': True, 'is_template': False, 'web_commit_signoff_required': False, 'topics': [], 'visibility': 'public', 'forks': 0, 'open_issues': 5, 'watchers': 0, 'default_branch': 'main'}, 'sender': {'login': 'lil-jr-dev[bot]', 'id': 141794476, 'node_id': 'BOT_kgDOCHOcrA', 'avatar_url': 'https://avatars.githubusercontent.com/in/373429?v=4';, 'gravatar_id': '', 'url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D';, 'html_url': 'https://github.com/apps/lil-jr-dev';, 'followers_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/followers';, 'following_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/following{/other_user}', 'gists_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/gists{/gist_id}', 'starred_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/starred{/owner}{/repo}', 'subscriptions_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/subscriptions';, 'organizations_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/orgs';, 'repos_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/repos';, 'events_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/events{/privacy}', 'received_events_url': 'https://api.github.com/users/lil-jr-dev%5Bbot%5D/received_events';, 'type': 'Bot', 'site_admin': False}, 'installation': {'id': 40525268, 'node_id': 'MDIzOkludGVncmF0aW9uSW5zdGFsbGF0aW9uNDA1MjUyNjg='}}

  await handle_github_event(payload)

  return '', 200


async def main():
  # await handle_github_event()
  f = open('UIUC-Chatbot/ai-ta-backend/sample.json')
  payload = json.load(f)
  await handle_github_event(payload)
  pass


if __name__ == '__main__':
  #app.run(debug=True, port=os.getenv("PORT", default=8000))
  asyncio.run(main())
