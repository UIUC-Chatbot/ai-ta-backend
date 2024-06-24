"""
To deploy: beam deploy usage_analysis.py
Use CAII gmail to auth.
"""

import os
import json
import supabase
import requests
from datetime import datetime
from typing import Any, Dict, List
import beam
from beam import App, QueueDepthAutoscaler, Runtime
from posthog import Posthog

requirements = [
    "posthog==3.1.0",
    "supabase==2.0.2",
]

app = App(
    "usage_analysis",
    runtime=Runtime(
        cpu=1,
        memory="2Gi",
        image=beam.Image(
            python_version="python3.10",
            python_packages=requirements,
        ),
    ))

def loader():
    """
    The loader function will run once for each worker that starts up. https://docs.beam.cloud/deployment/loaders
    """
    posthog = Posthog(sync_mode=True, project_api_key=os.environ['POSTHOG_API_KEY'], host='https://app.posthog.com')
    supabase_client = supabase.create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_API_KEY']) # type: ignore

    return posthog, supabase_client

autoscaler = QueueDepthAutoscaler(max_tasks_per_replica=2, max_replicas=3)


@app.task_queue(
    workers=1,
    max_pending_tasks=15_000,
    max_retries=3,
    timeout=-1,
    loader=loader,
    autoscaler=autoscaler)
def usage_analysis(**inputs: Dict[str, Any]):
    """
    This function queries supabase for the latest usage data and sends it to Posthog.
    Details to report: 
    Args:
        course_name (str): The name of the course.
    """
    course_name = str = inputs.get('course_name', '')
    print("Running usage analysis for course:", course_name)
    
    posthog_client, supabase_client = inputs['context']

    if course_name:
        # single course
        print("Single course")
        metrics = get_usage_data(course_name, supabase_client)
        print("Metrics:", metrics)

        # upload to Supabase
        response = supabase_client.table('usage_metrics').insert(metrics).execute()
        print("Response:", response)

    else:
        # all courses
        print("All courses")

    return "Success"

def get_usage_data(course_name, supabase_client) -> Dict[str, Any]:
    """
    Get usage data from Supabase.
    """
    # get total documents
    total_docs = supabase_client.table('documents').select('id', count='exact').eq('course_name', course_name).execute()
    print("Total docs:", total_docs.count)

    # get total conversations
    total_conversations = supabase_client.table('llm-convo-monitor').select('id', count='exact').eq('course_name', course_name).execute()
    print("Total conversations:", total_conversations.count)

    # get most recent conversation
    most_recent_conversation = supabase_client.table('llm-convo-monitor').select('id', 'created_at').eq('course_name', course_name).order('created_at', desc=True).limit(1).execute()
    print("Most recent conversation:", most_recent_conversation)

    # extract datetime 
    print(type(most_recent_conversation.data[0]['created_at']))
    dt_str = most_recent_conversation.data[0]['created_at']
    dt_object = datetime.fromisoformat(dt_str)

    metrics = {
        "course_name": course_name,
        "total_docs": total_docs.count,
        "total_convos": total_conversations.count,
        "most_recent_convo": dt_str,
    }

    return metrics

