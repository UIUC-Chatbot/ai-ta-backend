import os
import json
import requests
import pandas as pd
from supabase import create_client, Client
from ai_ta_backend.database.vector import VectorDatabase
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()


# create Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_API_KEY")
supabase_client = create_client(supabase_url, supabase_key)



def webscrape_documents(project_name: str):
    print(f"Scraping documents for project: {project_name}")
    
    # use RPC to get unique base_urls
    response = supabase_client.rpc("get_distinct_base_urls", {"p_course_name": project_name}).execute()
    print(f"Base urls: {response}")
    base_urls = response.data
    print(f"Total base_urls: {len(base_urls)}")
    
    #webcrawl_url = "https://crawlee.kastan.ai/crawl"
    webcrawl_url = "https://crawlee-production.up.railway.app/crawl"
    payload = {
        "params": {
            "url": "",
            "scrapeStrategy": "equal-and-below",
            "match": "",
            "maxPagesToCrawl": 50,
            "maxTokens": 2000000,
            "courseName": project_name
        }
    }

    for base_url in base_urls:
        payload["params"]["url"] = base_url
        domain = urlparse(base_url).netloc
        print(f"Domains: {domain}")
        payload["params"]["match"] = "http?(s)://" + domain + "/**"
        #response = requests.post(webcrawl_url, json=payload)
        print("Response from crawl: ", response.json())

        # print("Payload: ", payload)

        

    return "Webscrape done."