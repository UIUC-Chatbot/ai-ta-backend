import os
from bs4 import BeautifulSoup
import requests
import re
import time
from selenium import webdriver

# Check if the url is valid
# Else return the status code

def valid_url(url):
	
	# exception block
	try:
	
		# pass the url into
		# request.hear
		response = requests.head(url)
		
		# check the status code
		if response.status_code == 200:
			return True
		else:
			return response.status_code
	except requests.ConnectionError as e:
		return e

# Function gets titles of urls and the urls themselves
def get_urls_dict(url:str):

    site= re.match(pattern=r'https:\/\/[a-zA-Z0-9.]*[a-z]', string=url).group(0)

    # Gets rid of double slashes
    url = re.sub(pattern=r"https:\/\/", repl="", string=url)
    url = re.sub(pattern=r"[\/\/]{2,}", repl="", string=url)
    url = "https://"+url

    urls= {}

    r = requests.get(url)
    s = BeautifulSoup(r.text,"html.parser")

    for i in s.find_all("a"):

        # text/label inside the tag for url
        text = i.text

        # regex to clean \n and \r from text
        text = re.sub(r'[\n\r]', '', text)
        text = text.strip()
        
        try:
        # getting the href tag
            href = i.attrs['href']
        except KeyError as e:
            print("KeyError:", e, "for", i)
            continue
    
        if href.startswith("http"):
            pass
            
        # This line doesn't matter because the amount of slashes doesn't change the site, but leave it in for now
        elif href.startswith("/"):
            href = site+href
        else:
            href = site+'/'+href
        urls[text] = href    
    return urls


# Gathers all of the connected urls from the base url
def site_map(base_url:str, max_urls:int=1000, max_depth:int=3, _depth:int=0, _invalid_urls:list=[]):
    # Prints the depth of the current search
    print("depth: ", _depth)
    all = []
    amount = max_urls

    # If the base url is valid, then add it to the list of urls and get the urls from the base url
    if valid_url(base_url) == True:

        urls = list(get_urls_dict(base_url).values())

        if len(urls) <= max_urls:
            all.extend(urls)
        else:
            all.extend(urls[:max_urls])
    else:
        print("Invalid URL", base_url + ",", "Status Code:",valid_url(base_url))
        _invalid_urls.append(base_url)

    # Create the new amount of max urls for the next function call
    all = list(set(all))
    max_urls = max_urls - len(all)

    # Recursively call the function on all of the urls found in the base url
    for url in all:
        if url not in _invalid_urls:
            if valid_url(url) == True:
                if max_urls > 0:
                    if _depth < max_depth:
                        all.extend(site_map(url, max_urls, max_depth, _depth+1, _invalid_urls))
                        all = list(set(all))
                        max_urls = max_urls - len(all)
                    else:
                        print("Depth exceeded:", _depth+1, "out of", max_depth)
                        break
                else:
                    break
            else:
                print("Invalid URL", url + ',', "Status Code:",valid_url(url))
                _invalid_urls.append(url)
                continue
        else:
            continue
  
    all = list(set(all))

    if len(all) < amount and _depth == 0:
        print("Max URLS not reached, returning all urls found:", len(all), "out of", amount)
        return all
    elif len(all) == amount and _depth == 0:
        print("Max URLS reached:", len(all), "out of", amount)
        return all

    return all

# Function to get the text from a url
def scraper(url:str):
    r = requests.get(url)
    soup = BeautifulSoup(r.text,"html.parser")
    
    for tag in soup(['header', 'footer', 'nav', 'aside']):
        tag.decompose()
    
    return soup

# Uses all of above functions to crawl a site
def crawler(site:str, max_urls:int=1000, max_depth:int=3, timeout:int=1):
    all_sites = site_map(site, max_urls, max_depth)
    crawled = {}
    invalid_urls = []

    for site in all_sites:
        try:
            soup = scraper(site)
            crawled[site] = soup.get_text()
            time.sleep(timeout)
        
        except Exception as e:
            print("url:", site, "Exception:", e)
            invalid_urls.append(site)
            continue
    
    # Delete repeated values
    for value in crawled.values():
        if list(crawled.values()).count(value) > 1:
            for key in crawled.keys():
                if crawled[key] == value:
                    del crawled[key]
                    break

    return crawled

# Download a course using its url
def mit_course_download(url:str, save_path:str, ):
    base = "https://ocw.mit.edu"
    if url.endswith("download"):
        pass
    else:
        url = url + "download"

    r = requests.get(url)
    soup = BeautifulSoup(r.text,"html.parser")

    zip = ''
    for ref in soup.find_all("a"):
        if ref.attrs['href'].endswith("zip"):
            zip = ref.attrs['href']
    
    site =  zip
    print('site', site)
    r = requests.get(url=site, stream=True)

    try:
        with open(save_path, 'wb') as fd:
            for chunk in r.iter_content(chunk_size=128):
                fd.write(chunk)
    
        print("course downloaded!")
    
    except Exception as e:
        print("Error:", e, site)
    