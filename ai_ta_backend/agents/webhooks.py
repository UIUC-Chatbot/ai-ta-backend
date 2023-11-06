import docker
import json
import os
import os

from github import Auth, GithubIntegration
from github.Issue import Issue
from github.PullRequest import PullRequest
from github.Repository import Repository
from langchain import hub
from supabase.client import create_client

# Initialize Supabase client
supabase_url = os.environ["SUPABASE_URL"]
supabase_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
supabase = create_client(supabase_url, supabase_key)

# Initialize Docker client
docker_client = docker.from_env()

def check_and_insert_image_name(image_name):
    """Check if the image name exists in the Supabase table, if not, insert it.

    Args:
        image_name (str): The Docker image name.
    """
    # Query the Supabase table
    result = supabase.table("docker_images").select("image_name").eq("image_name", image_name).execute()

    # If the image name does not exist in the table, insert it
    if not result["data"]:
        supabase.table("docker_images").insert({"image_name": image_name}).execute()

def handle_event(payload, event_type):
    """ This is the primary entry point to the app; Just open an issue!

    Args:
        payload (_type_): From github, see their webhook docs.
        event_type (str): The type of the event. Can be 'issue', 'pull_request', or 'comment'.
    """
    # Construct Docker image name
    repo_name = payload["repository"]["full_name"]
    number = payload.get('issue').get('number')
    image_name = f"{repo_name}_{number}"

    # Check if the image name exists in the Supabase table, if not, insert it
    check_and_insert_image_name(image_name)

    # Send shell command to Docker image
    command = f"python github_webhook_handlers.py --payload '{json.dumps(payload)}'"
    docker_client.containers.run(image_name, command)

def handle_issue_opened(payload):
    handle_event(payload, 'issue')

def handle_pull_request_opened(payload):
    handle_event(payload, 'pull_request')

def handle_comment_opened(payload):
    handle_event(payload, 'comment')
