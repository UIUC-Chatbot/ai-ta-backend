import requests
import concurrent.futures
import time

SCRAPE_LOG = {}

def crawlee_scrape(course_name: str, urls: list, exclude_urls: list, match_url: str):
    """
    This function takes in a pre-defined set of URLs and scrapes the content from each URL.
    """
    print("Scraping URLs:", urls)
    
    payload = {
            "params": {
                "url": "",
                "scrapeStrategy": "equal-and-below",
                "match": "",
                "maxPagesToCrawl": 15000,
                "maxTokens": 2000000,
                "maxConcurrency": 20,
                "maxRequestsPerMinute": 120,
                "courseName": course_name,
                "exclude": exclude_urls
            }
    }

    # create a POST request to the crawlee API
    api_endpoint = 'https://crawlee-production.up.railway.app/crawl'

    # loop through the URLs and scrape the content
    for url in urls:
        payload["params"]["url"] = url

        if match_url:
            payload["params"]["match"] = match_url
        else:
            payload["params"]["match"] = "http?(s)://" + url.split("//")[1] + "/**"
        
        print("Scraping URL:", url)
        start_time = time.monotonic()
        response = requests.post(api_endpoint, json=payload)
        
        try:
            no_of_urls_scraped = response.json()
            SCRAPE_LOG[url] = no_of_urls_scraped
        except Exception as e:
            print(f"Error: {e}")
            
        print(f"⏰ Scraping runtime: {(time.monotonic() - start_time):.2f} seconds")
        time.sleep(10)
    
    print(SCRAPE_LOG)

    return "Scraping complete."

# parallel version of the above function

# def crawlee_scrape(course_name: str):
#     """
#     This function takes in a pre-defined set of URLs and scrapes the content from each URL.
#     """
#     urls = [
#         'https://extension.uga.edu'
        
#     ]

#     payload = {
#             "params": {
#                 "url": "",
#                 "scrapeStrategy": "equal-and-below",
#                 "match": "",
#                 "maxPagesToCrawl": 5000,
#                 "maxTokens": 2000000,
#                 "courseName": course_name
#             }
#     }

#     # create a POST request to the crawlee API
#     api_endpoint = 'https://crawlee-production.up.railway.app/crawl'

#     with concurrent.futures.ThreadPoolExecutor() as executor:
#         futures = []
#         for url in urls:
#             future = executor.submit(scrape_url, url, payload, api_endpoint)
#             futures.append(future)

#         # Wait for all tasks to complete and gather results
#         for future in concurrent.futures.as_completed(futures):
#             result = future.result()
#             print(result)

#     print(SCRAPE_LOG)

#     return "Scraping complete."


# def scrape_url(url, payload, api_endpoint):
#     """
#     Scrapes a single URL and logs results.
#     """

#     payload["params"]["url"] = url
#     payload["params"]["match"] = "http?(s)://" + url.split("//")[1] + "/**"

#     print("Scraping URL:", url)
#     start_time = time.monotonic()
#     response = requests.post(api_endpoint, json=payload)

#     #no_of_urls_scraped = response.json()
#     #SCRAPE_LOG[url] = no_of_urls_scraped

#     no_of_urls_scraped = response.text

#     print(f"⏰ Scraping runtime: {(time.monotonic() - start_time):.2f} seconds")

#     return f"Scraped {url} with {no_of_urls_scraped} URLs scraped."

