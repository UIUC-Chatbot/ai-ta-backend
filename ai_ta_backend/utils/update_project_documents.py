import os
import json
import requests
import pandas as pd
from supabase import create_client, Client
from ai_ta_backend.database.vector import VectorDatabase
from dotenv import load_dotenv
from urllib.parse import urlparse


load_dotenv()

def webscrape_documents(project_name: str):
    print(f"Scraping documents for project: {project_name}")

    # get unique base_urls
    # base_url_df = pd.read_csv(filepath_or_buffer="./cropwizard_base_urls2.csv")
    # base_urls = base_url_df['base_url'].unique()

    base_urls = [
    "https://farmdocdaily.illinois.edu/category/areas",
    "https://extension.illinois.edu/sites/default/files/managing_diseases_2022web.pdf",
    "https://extension.illinois.edu/newsletters/illinois-pesticide-review-newsletter/januaryfebruary-2023",
    "https://farmdocdaily.illinois.edu/2023/08/farm-bill-2023-is-there-bad-medicine-in-base-acres-and-reference-prices.html",
    "https://ipcm.wisc.edu/wp-content/uploads/sites/54/2022/11/SeasonalGuide_FINAL.pdf",
    "https://extension.illinois.edu/global/agronomy-handbook",
    "https://extension.illinois.edu/newsletters/illinois-pesticide-review-newsletter/septemberoctober-2022",
    "https://ipcm.wisc.edu/blog/2023/08/wisconsin-datcp-field-notes-aug-10/",
    "https://extension.illinois.edu/newsletters/illinois-pesticide-review-newsletter/novemberdecember-2022",
    "https://ipcm.wisc.edu/wcm/",
    "https://farmdocdaily.illinois.edu/2023/09/conventional-and-organic-enterprise-net-returns-4.html",
    "https://extension.illinois.edu/newsletters/illinois-pesticide-review-newsletter/julyaugust-2023",
    "https://extension.illinois.edu/sites/default/files/2022_arb_compiled_accessibility_20230131.pdf",
    "https://extension.illinois.edu/newsletters/illinois-pesticide-review-newsletter/marchapril-2023-0",
    "https://extension.illinois.edu/newsletters/illinois-pesticide-review-newsletter/mayjune-2023"
    ]

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
        response = requests.post(webcrawl_url, json=payload)
        print("Response from crawl: ", response.json())

        # print("Payload: ", payload)

        

    return "Webscrape done."