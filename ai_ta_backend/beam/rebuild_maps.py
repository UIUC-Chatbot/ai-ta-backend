import os
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Union
import beam
import boto3
import openai
import sentry_sdk
import supabase
import nomic
import requests
from nomic.project import AtlasClass
from beam import App, QueueDepthAutoscaler, Runtime  # RequestLatencyAutoscaler,

from PIL import Image
from posthog import Posthog


requirements = [
    "openai<1.0",
    "supabase==2.0.2",
    "tiktoken==0.5.1",
    "boto3==1.28.79",
    "qdrant-client==1.7.3",
    "langchain==0.0.331",
    "posthog==3.1.0",
    "pysrt==1.1.2",
    "docx2txt==0.8",
    "pydub==0.25.1",
    "ffmpeg-python==0.2.0",
    "ffprobe==0.5",
    "ffmpeg==1.4",
    "PyMuPDF==1.23.6",
    "pytesseract==0.3.10",  # image OCR"
    "openpyxl==3.1.2",  # excel"
    "networkx==3.2.1",  # unused part of excel partitioning :("
    "python-pptx==0.6.23",
    "unstructured==0.10.29",
    "GitPython==3.1.40",
    "beautifulsoup4==4.12.2",
    "sentry-sdk==1.39.1",
    "nomic==2.0.14",
]

# TODO: consider adding workers. They share CPU and memory https://docs.beam.cloud/deployment/autoscaling#worker-use-cases
app = App("rebuild_maps",
          runtime=Runtime(
              cpu=1,
              memory="3Gi",
              image=beam.Image(
                  python_version="python3.10",
                  python_packages=requirements,
                  commands=["apt-get update && apt-get install -y ffmpeg tesseract-ocr"],
              ),
          ))

# MULTI_QUERY_PROMPT = hub.pull("langchain-ai/rag-fusion-query-generation")
OPENAI_API_TYPE = "azure"  # "openai" or "azure"


def loader():
  """
  The loader function will run once for each worker that starts up. https://docs.beam.cloud/deployment/loaders
  """
  openai.api_key = os.getenv("VLADS_OPENAI_KEY")
  nomic.login(os.getenv('NOMIC_API_KEY'))

  # Create a Supabase client
  supabase_client = supabase.create_client(  # type: ignore
      supabase_url=os.environ['SUPABASE_URL'], supabase_key=os.environ['SUPABASE_API_KEY'])

  posthog = Posthog(sync_mode=True, project_api_key=os.environ['POSTHOG_API_KEY'], host='https://app.posthog.com')
  sentry_sdk.init(
      dsn="https://examplePublicKey@o0.ingest.sentry.io/0",

      # Enable performance monitoring
      enable_tracing=True,
  )

  return supabase_client, posthog


# autoscaler = RequestLatencyAutoscaler(desired_latency=30, max_replicas=2)
autoscaler = QueueDepthAutoscaler(max_tasks_per_replica=300, max_replicas=3)

def rebuild_maps(supabase_client, posthog):
    """
    This rebuild all maps in Nomic dashboard.
    1. Get a list of all maps from Nomic.
    2. For each map, check last inserted entry in Supabase.
    3. If the last entry is older than 3 months, skip rebuild, otherwise re-build the map.
    """
    nomic_projects = list_projects()


    return "success"



def list_projects(organization_id=None):
    """
    Lists all projects in an organization.

    If called without an organization id, it will list all projects in the
    current user's main organization.
    """
    c = AtlasClass()
    if organization_id is None:
        organization = c._get_current_users_main_organization()
        if organization is None:
            raise ValueError(
                "No organization id provided and no main organization found."
            )
        organization_id = organization['organization_id']
    response = requests.get(
        c.atlas_api_path + f"/v1/organization/{organization_id}",
        headers=c.header
    )
    proj_info = response.json()['projects']
    return [
        {'name': p['project_name'],
            'id': p['id'],
            'created_timestamp': p['created_timestamp']}
        for p in proj_info
    ]