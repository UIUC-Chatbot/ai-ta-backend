import docker
import json
import os

from supabase.client import create_client
from docker.errors import NotFound

# Initialize Supabase client
supabase_url = os.environ["SUPABASE_URL"]
supabase_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
supabase = create_client(supabase_url, supabase_key)

# Initialize Docker client
docker_client = docker.from_env()

def build_docker_image(image_name):
    """Build a Docker image with the given name.

    Args:
        image_name (str): The Docker image name.
    """
    dockerfile_path = '.'  # replace with the path to your Dockerfile
    docker_client.images.build(path=dockerfile_path, tag=image_name)

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
    docker_client.containers.run(image_name, command, volumes={volume.name: {'bind': '/app', 'mode': 'rw'}}) #type:ignore

def check_and_insert_image_name(image_name):
    """Check if the image name exists in the Supabase table, if not, insert it and build a Docker image.

    Args:
        image_name (str): The Docker image name.
    """
    # Query the Supabase table
    result = supabase.table("docker_images").select("image_name").eq("image_name", image_name).execute()

    # If the image name does not exist in the table, insert it and build a Docker image
    if not result["data"]:
        supabase.table("docker_images").insert({"image_name": image_name}).execute()
        build_docker_image(image_name)

    # Query the Docker environment
    docker_images = [img.tags[0] for img in docker_client.images.list()] #type:ignore

    # Check if the image exists in the Docker environment
    if image_name not in docker_images:
        raise ValueError(f"Docker image {image_name} does not exist in the Docker environment.")

def handle_event(payload):
    """ This is the primary entry point to the app; Just open an issue!

    Args:
        payload (_type_): From github, see their webhook docs.
    """
    # Construct Docker image name
    repo_name = payload["repository"]["full_name"]
    number = payload.get('issue').get('number')
    image_name = f"{repo_name}_{number}"
    volume_name = f"vol_{image_name}"

    # Check if the image name exists in the Supabase table, if not, insert it and build a Docker image
    check_and_insert_image_name(image_name)

    # Send shell command to Docker image
    command = f"python github_webhook_handlers.py --payload '{json.dumps(payload)}'"
    run_docker_container(image_name, command, volume_name)
