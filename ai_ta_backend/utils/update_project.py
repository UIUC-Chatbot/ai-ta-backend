from concurrent.futures import as_completed
import os
from supabase import create_client
from dotenv import load_dotenv
from urllib.parse import urlparse
import json
import requests
from ai_ta_backend.executors.thread_pool_executor import ThreadPoolExecutorAdapter

load_dotenv()

def send_request(webcrawl_url, payload):
    response = requests.post(webcrawl_url, json=payload)
    return response.json()

def webscrape_documents(project_name: str):
    print(f"Scraping documents for project: {project_name}")

    # create Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_API_KEY")
    supabase_client = create_client(supabase_url, supabase_key)

    # use RPC to get unique base_urls
    response = supabase_client.rpc("get_base_url_with_doc_groups", {"p_course_name": project_name}).execute()
    base_urls = response.data
    print(f"Total base_urls: {len(base_urls)}")

    webcrawl_url = "https://crawlee-production.up.railway.app/crawl"

    payload = {
        "params": {
            "url": "",
            "scrapeStrategy": "same-hostname",
            "maxPagesToCrawl": 15000,
            "maxTokens": 2000000,
            "courseName": project_name
        }
    }

    tasks = []
    count = 0
    batch_size = 10

    with ThreadPoolExecutorAdapter(max_workers=batch_size) as executor:
        for base_url in base_urls:
            document_groups = base_urls[base_url]
            payload["params"]["url"] = base_url
            if not document_groups:
                continue

            # Read the file process_urls.txt and skip all the URLs mentioned there
            with open('process_urls.txt', 'r') as file:
                skip_urls = set(line.strip() for line in file)

            if base_url in skip_urls:
                print(f"Skipping URL: {base_url}")
                continue

            domain = urlparse(base_url).netloc
            payload["params"]["documentGroups"] = base_urls[base_url]
            print("Payload: ", payload)

            if not os.path.exists('process_urls.txt'):
                open('process_urls.txt', 'w').close()

            with open('process_urls.txt', 'a') as file:
                file.write(base_url + '\n')

            tasks.append(executor.submit(send_request, webcrawl_url, payload.copy()))
            count += 1

            if count % batch_size == 0:
                for future in as_completed(tasks):
                    response = future.result()
                    print("Response from crawl: ", response)
                tasks = []

        # Process remaining tasks
        for future in as_completed(tasks):
            response = future.result()
            print("Response from crawl: ", response)

    return "Webscrape done."