import docker
import json
import os

from supabase.client import create_client
from docker.errors import NotFound, BuildError, ContainerError, ImageNotFound, APIError
import traceback
import re
import logging
import shlex
# Initialize Supabase client
supabase_url = os.environ["SUPABASE_URL"]
supabase_key = os.environ["SUPABASE_API_KEY"]
supabase = create_client(supabase_url, supabase_key)

# Initialize Docker client
docker_client = docker.from_env()
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('docker').setLevel(logging.DEBUG)
logging.getLogger('urllib3').setLevel(logging.DEBUG)

def build_docker_image(image_name):
    """Build a Docker image with the given name.

    Args:
        image_name (str): The Docker image name.
    """
    print(f"Building docker image: {image_name}")
    dockerfile_path = "ai_ta_backend/agents"
    try:
        img, logs = docker_client.images.build(path=dockerfile_path, tag=image_name, quiet=False) #type:ignore
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

def check_and_insert_image_name(image_name):
    """Check if the image name exists in the Supabase table, if not, insert it and build a Docker image.

    Args:
        image_name (str): The Docker image name.
    """
    docker_images = []
    img = None
    # Query the Supabase table
    result = supabase.table("docker_images").select("image_name").eq("image_name", image_name).execute()

    print(f"Result: {result}")

    # If the image name does not exist in the table, insert it and build a Docker image
    if not result.data:
        supabase.table("docker_images").insert({"image_name": image_name}).execute()
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
        # If the image already exists, fetch it
        img = docker_client.images.get(image_name)

    return img


def handle_event(payload):
    """ This is the primary entry point to the app; Just open an issue!

    Args:
        payload (_type_): From github, see their webhook docs.
    """
    # Convert raw_payload to a JSON string
    payload_json = json.dumps(payload)
    # print(f"Payload in webhooks: {payload_json}")

    # Construct Docker image name
    repo_name = payload["repository"]["full_name"].lower()
    number = payload.get('issue').get('number')
    image_name = f"{repo_name}_{number}"
    # Filter out disallowed characters from the image name for the volume name
    volume_name = f"vol_{re.sub('[^a-zA-Z0-9_.-]', '_', image_name)}"

    # Check if the image name exists in the Supabase table, if not, insert it and build a Docker image
    img = check_and_insert_image_name(image_name)

    # Send shell command to Docker image
    command = f"python github_webhook_handlers.py --payload {shlex.quote(payload_json)}"

    print(f"Command for container: {command}")
    if img:
        run_docker_container(image_name, command, volume_name)
