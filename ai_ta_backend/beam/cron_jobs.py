"""
CRON job functions to update conversation and document maps in Nomic. 
Run twice a day.
"""

# Call /updateConversationMap and /updateDocumentMap endpoints in Nomic

import requests
import os
from beam import schedule


@schedule(when="@daily", name="update-nomic-maps")
def task():
    print("Hi, from your task running at 11:00 AM daily!")
    base_url = "https://flask-pr-328.up.railway.app"

    # Update conversation maps
    url = f"{base_url}/updateConversationMaps"
    response = requests.get(url)

    if response.status_code == 200:
        print("Conversation maps updated successfully")
    else:
        print("Failed to update conversation maps")

    # Update document maps
    url = f"{base_url}/updateDocumentMaps"
    response = requests.get(url)
    
    if response.status_code == 200:
        print("Document maps updated successfully")
    else:
        print("Failed to update document maps")

    return "Task completed successfully"
