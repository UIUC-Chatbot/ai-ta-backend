import os
import json
import requests
import pandas as pd
from supabase import create_client, Client
from ai_ta_backend.database.vector import VectorDatabase
from dotenv import load_dotenv

load_dotenv()

url: str = "https://supa.ncsa.ai"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.ewogICJyb2xlIjogInNlcnZpY2Vfcm9sZSIsCiAgImlzcyI6ICJzdXBhYmFzZSIsCiAgImlhdCI6IDE3MzA5MzQwMDAsCiAgImV4cCI6IDE4ODg3MDA0MDAKfQ.gNbdOlPCo4oAN7Zx5Lc0RXbYk-kXFfX0iMq0p09D-H0"
supabase_client: Client = create_client(url, key)

def webscrape_documents(project_name: str):
    print(f"Scraping documents for project: {project_name}")

    # get unique base_urls
    base_url_df = pd.read_csv(filepath_or_buffer="./cropwizard_base_urls2.csv")
    base_urls = base_url_df['base_url'].unique()

    print(f"Base URLs: {base_urls}")


    return "Webscrape done."