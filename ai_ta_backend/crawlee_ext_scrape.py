import requests
import os
import json
import time

SCRAPE_LOG = {}

def crawlee_scrape(course_name: str):
    """
    This function takes in a pre-defined set of URLs and scrapes the content from each URL.
    """
    urls = [
        'https://extension.arizona.edu/'
    ]

    payload = {
            "params": {
                "url": "",
                "scrapeStrategy": "equal-and-below",
                "match": "",
                "maxPagesToCrawl": 20000,
                "maxTokens": 2000000,
                "courseName": course_name
            }
    }

    # create a POST request to the crawlee API
    api_endpoint = 'https://crawlee-production.up.railway.app/crawl'

    # loop through the URLs and scrape the content
    for url in urls:
        payload["params"]["url"] = url
        payload["params"]["match"] = "http?(s)://" + url.split("//")[1] + "/**"
        
        print("Scraping URL:", url)
        start_time = time.monotonic()
        response = requests.post(api_endpoint, json=payload)
        
        no_of_urls_scraped = response.json()
        SCRAPE_LOG[url] = no_of_urls_scraped
        print(f"⏰ Scraping runtime: {(time.monotonic() - start_time):.2f} seconds")
        time.sleep(10)
    
    print(SCRAPE_LOG)

    return "Scraping complete."

