import os
import pandas as pd
import requests
import json
import supabase
import sentry_sdk
from posthog import Posthog
from beam import App, Image, Runtime, QueueDepthAutoscaler


requirements = ["pandas", "supabase==2.0.2", "posthog==3.1.0", "sentry-sdk==1.39.1"]
app = App("project_analysis",
          runtime=Runtime(
              cpu=1,
              memory="3Gi",
              image=Image(
                  python_version="python3.10",
                  python_packages=requirements,
                  commands=["apt-get update && apt-get install -y ffmpeg tesseract-ocr"],
              ),
          ))

def loader():
    supabase_client = supabase.create_client(  # type: ignore
      supabase_url=os.environ['SUPABASE_URL'], supabase_key=os.environ['SUPABASE_API_KEY'])
    
    posthog = Posthog(sync_mode=True, project_api_key=os.environ['POSTHOG_API_KEY'], host='https://app.posthog.com')
    sentry_sdk.init(
      dsn=os.getenv("SENTRY_DSN"),
      # Set traces_sample_rate to 1.0 to capture 100% of transactions for performance monitoring.
      traces_sample_rate=1.0,
      # Set profiles_sample_rate to 1.0 to profile 100% of sampled transactions.
      # We recommend adjusting this value in production.
      profiles_sample_rate=1.0,
      enable_tracing=True)

autoscaler = QueueDepthAutoscaler(max_tasks_per_replica=300, max_replicas=3)


def analyze_project():
    """
    Function to consolidate document and conversation data
    for all projects
    """
    # get distinct projects from Vercel KV
    vercel_url = os.environ['VERCEL_HKEYS_URL'] + "/course_metadatas"
    headers = {"Authorization": f"Bearer {os.environ['VERCEL_READ_ONLY_API_KEY']}", "Content-Type": "application/json"}
    response = requests.get(vercel_url, headers=headers)
    response = response.json()
    projects_list = response['result']
    print(projects_list)

    return "success"
