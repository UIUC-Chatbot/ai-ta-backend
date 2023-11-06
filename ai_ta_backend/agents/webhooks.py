import docker
import json
import os

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

def handle_event(payload):
    """ This is the primary entry point to the app; Just open an issue!

    Args:
        payload (_type_): From github, see their webhook docs.
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
