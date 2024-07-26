import os
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import crossref_commons

def extract_article_metadata(search_str: str) -> str:
    """
    Extract article metadata from NAL website.
    Store the metadata in a SQL database.
    """
    print("Extracting article metadata from NAL website...")

    # get list of articles - 1st page
    search_results = get_search_results(search_str)

    # for each article, go one level deeper to extract DOI
    search_results = extract_doi(search_results)

    # fetch metadata for each DOI using crossref API
    for article in search_results:
        doi = article['doi']
        if doi != "N/A":
            metadata = get_article_metadata_from_crossref(doi)
            article['doi_number'] = doi
            article['publisher'] = metadata['publisher']
            
            if 'license' in metadata:
                print("license: ", metadata['license'])
            
                for ele in metadata['license']:
                    if ele['content-version'] == 'tdm':
                        article['license'] = ele['URL']
                        break
                # if license is still empty, go for vor
                if 'license' not in article:
                    for ele in metadata['license']:
                        if ele['content-version'] == 'vor':
                            article['license'] = ele['URL']
                            break
                else:
                    article['license'] = "N/A"
                    
            else:
                article['license'] = "N/A"   

            article['metadata'] = metadata   

            print("Article: ", article)
            
    print("Full list of articles: ", search_results)        
    return "Article metadata extracted successfully."


def get_search_results(query):
    # Set up Selenium with Chrome WebDriver
    chrome_binary_path = "C:/Program Files/Google/Chrome/Application/chrome.exe"
    chrome_options = Options()
    chrome_options.binary_location = chrome_binary_path

    chrome_options.add_argument("--headless")  # Run in headless mode (no GUI)
    chrome_options.add_argument("--disable-gpu")  # Disable GPU acceleration
    chrome_options.add_argument("--no-sandbox")  # Required for running as root
    chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems


    # Use ChromeDriverManager to automatically manage the driver
    driver_service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=driver_service, options=chrome_options)

    try:
        # Construct the URL with the query
        base_url = "https://search.nal.usda.gov/discovery/search"
        params = f"?query=any,contains,{query}&tab=pubag&search_scope=pubag&vid=01NAL_INST:MAIN&facet=tlevel,include,open_access&offset=0"
        url = base_url + params
        print("URL: ", url)
        # Load the page
        driver.get(url)
        
        # Wait for the page to load (you may need to adjust the sleep time)
        time.sleep(20)
        
        # Find the search results
        results = driver.find_elements(By.CLASS_NAME, 'list-item')
        print("Results: ", len(results))
        
        # Extract the titles and links
        search_results = []
        for result in results:
            title_element = result.find_element(By.CLASS_NAME, 'item-title')
            title = title_element.text.strip()
            link = title_element.find_element(By.TAG_NAME, 'a').get_attribute('href')
            search_results.append({'title': title, 'link': link})
        
        return search_results
    finally:
        # Close the browser
        driver.quit()

def extract_doi(article_list: list):
    """
    Extract DOI from the article page and append to article_list dictionary.
    """
    # Set up Selenium with Chrome WebDriver
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode (no GUI)
    chrome_options.add_argument("--disable-gpu")  # Disable GPU acceleration
    chrome_options.add_argument("--no-sandbox")  # Required for running as root
    chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems

    # Use ChromeDriverManager to automatically manage the driver
    driver_service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=driver_service, options=chrome_options)

    for item in article_list:
        page_link = item['link']

        # Load the page
        driver.get(page_link)
            
        # Wait for the page to load (you may need to adjust the sleep time)
        time.sleep(20)
            
        # Find the search results
        results = driver.find_elements(By.ID, 'item-details')
        #print("Results: ", results)
            
        # Extract the titles and links
        for result in results:
                
            try:
                doi_link_element = result.find_element(By.XPATH, './/a[contains(@href, "https://doi.org/")]')
                doi_link = doi_link_element.get_attribute("href")
            except Exception as e:
                doi_link = "N/A"
            item['doi'] = doi_link

    # Close the browser
    driver.quit()

    return article_list


def get_article_metadata_from_crossref(doi: str):
    """
    Get article metadata from Crossref API.
    """
    # Get metadata from Crossref
    metadata = crossref_commons.retrieval.get_publication_as_json(doi)
    print("Metadata: ", metadata)
    
    return metadata

    

        