import docker
import json
import os
from dotenv import load_dotenv

from supabase.client import create_client
from docker.errors import NotFound, BuildError, ContainerError, ImageNotFound, APIError
import traceback
import re
import logging
import shlex
import uuid
from newrelic_telemetry_sdk import Log, LogClient

from ai_ta_backend.agents.utils import get_supabase_client, get_langsmith_id

load_dotenv(override=True, dotenv_path='.env')

# Initialize Docker client
try:
    docker_client = docker.from_env()
except Exception as e:
    print(f"Is your Docker client running? Error while setting up docker client: {e}")
    print(traceback.print_exc())
    
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('docker').setLevel(logging.DEBUG)
logging.getLogger('urllib3').setLevel(logging.INFO)

# Initialize New Relic Client
log_client = LogClient(os.environ['NEW_RELIC_LICENSE_KEY'])

def build_docker_image(image_name):
    """Build a Docker image with the given name.

    Args:
        image_name (str): The Docker image name.
    """
    print(f"Building docker image: {image_name}")
    dockerfile_path = "ai_ta_backend/agents"
    try:
        img, logs = docker_client.images.build(path=dockerfile_path, tag=image_name, quiet=False, nocache=True) #type:ignore
        print(f"Response on creating new image: {img.attrs}")
        for log in logs:
            if 'stream' in log:
                print(f"Build logs: {log['stream'].strip()}")
            elif 'error' in log:
                print(f"Error: {log['error']}")
        return img
    except BuildError as e:
        print(f"Error msg: {e.msg}")
        for log in e.build_log:
            if 'stream' in log:
                print(f"Build logs on error: {log['stream'].strip()}")
            elif 'error' in log:
                print(f"Error log: {log['error']}")
        print(traceback.print_exc())
    except Exception as e:
        print(f"Error: {e}")
        print(traceback.print_exc())
    return None

def run_docker_container(image_name, command, volume_name):
    """Run a Docker container with the given image name and command.

    Args:
        image_name (str): The Docker image name.
        command (str): The command to run in the Docker container.
        volume_name (str): The name of the Docker volume.
    """
    try:
        volume = docker_client.volumes.get(volume_name)
    except NotFound:
        # If the volume does not exist, create it
        volume = docker_client.volumes.create(name=volume_name)

    # Run a container with the volume attached
    try:
        docker_client.containers.run(image_name, command, volumes={volume.name: {'bind': '/app', 'mode': 'rw'}}) #type:ignore
    except ContainerError as e:
        print(f"Container error: {e.stderr}")
    except ImageNotFound as e:
        print(f"Image not found: {e.explanation}")
    except APIError as e:
        print(f"API error: {e.explanation}")
    except Exception as e:
        print(traceback.print_exc)

def check_and_insert_image_name(image_name, langsmith_run_id):
    """Check if the image name exists in the Supabase table, if not, insert it and build a Docker image.

    Args:
        image_name (str): The Docker image name.
    """
    docker_images = []
    img = None
    # Query the Supabase table
    supabase = get_supabase_client()
    result = supabase.table("docker_images").select("image_name").eq("image_name", image_name).execute()

    print(f"Result: {result}")

    # If the image name does not exist in the table, insert it and build a Docker image
    if not result.data:
        supabase.table("docker_images").insert({"image_name": image_name, "langsmith_id": langsmith_run_id}).execute()
        img = build_docker_image(image_name)

    # Query the Docker environment
    try:
        docker_images = [tag.split(":")[0] for img in docker_client.images.list() for tag in img.tags] #type:ignore
        print(f"Docker images available: {docker_images}")
    except Exception as e:
        print(f"An error occurred: {e}")

    # Check if the image exists in the Docker environment
    if image_name not in docker_images:
        print(f"Docker image {image_name} does not exist in the Docker environment.")
        img = build_docker_image(image_name)
    else:
        # If the image already exists, rebuild it to ensure it's up to date
        print(f"Rebuilding Docker image {image_name} to ensure it's up to date.")
        img = build_docker_image(image_name)  # This will use cache if no changes

    return img


def handle_event(payload):
    """ This is the primary entry point to the app; Just open an issue!

    Args:
        payload (_type_): From github, see their webhook docs.
    """
    # Convert raw_payload to a JSON string
    payload_json = json.dumps(payload)

    # Construct Docker image name
    repo_name = payload["repository"]["full_name"].lower()
    number = payload.get('issue').get('number')
    image_name = f"{repo_name}_{number}"
    
    # Filter out disallowed characters from the image name for the volume name
    volume_name = f"vol_{re.sub('[^a-zA-Z0-9_.-]', '_', image_name)}"

    langsmith_run_id = get_langsmith_id()

    # Check if the image name exists in the Supabase table, if not, insert it and build a Docker image
    img = check_and_insert_image_name(image_name, langsmith_run_id)

    # Send shell command to Docker image
    command = f"python github_webhook_handlers.py --payload {shlex.quote(payload_json)} --langsmith_run_id {langsmith_run_id}"

    print(f"Command for container: {command}")
    if img:
        run_docker_container(image_name, command, volume_name)
