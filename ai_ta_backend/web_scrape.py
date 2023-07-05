import os
import re
import time
from tempfile import NamedTemporaryFile

import boto3
import requests
from bs4 import BeautifulSoup

from ai_ta_backend.vector_database import Ingest

# Check if the url is valid
# Else return the status code

def valid_url(url):
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
  max_urls = int(max_urls)
  _depth = int(_depth)
  max_depth = int(max_depth)
  amount = max_urls

  # If the base url is valid, then add it to the list of urls and get the urls from the base url
  if valid_url(base_url) == True:
    all.append(base_url)
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
    # if url.startswith(base_url):
      # _invalid_urls.append(url)
      
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
    # else: 
    #   print(f"NOT SCRAPING URL outside our base_url.\n\tbase_url: {base_url}\n\turl:{url}")

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
    r = requests.get(url, cookies={'__hs_opt_out': 'no'})
    soup = BeautifulSoup(r.text,"html.parser")
    
    for tag in soup(['header', 'footer', 'nav', 'aside']):
        tag.decompose()
    
    return soup

def pdf_scraper(soup:BeautifulSoup): 
    links = soup.find_all('a')
    pdfs = [] 
    for link in links:
        if ('.pdf' in link.get('href', [])):

            # Get response object for link
            response = requests.get(link.get('href'))
            pdfs.append(response.content)
    return pdfs


# Uses all of above functions to crawl a site
def crawler(site:str, max_urls:int=1000, max_depth:int=3, timeout:int=1):
    all_sites = site_map(site, max_urls, max_depth)
    crawled = {}
    invalid_urls = []

    for site in all_sites:
        try:
            soup = scraper(site)
            crawled[site] = []
            crawled[site].append(soup.get_text())
            crawled[site].append(soup)
            crawled[site].append(pdf_scraper(soup))
            time.sleep(timeout)
            print("Scraped:", site)

        except Exception as e:
            print("Url Not Scraped!!!", "Exception:", e)
            invalid_urls.append(site)
            continue
    
    # Delete repeated values
    repeated = [value[0] for value in list(crawled.values())]
    for value in repeated:
        if repeated.count(value) > 1:
            for key in crawled.keys():
                if crawled[key][0] == value:
                    del crawled[key]
                    repeated.remove(value)
                    break

    print("Scraped", len(crawled), "urls out of", max_urls)

    return list(crawled.items())
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

# FIX BUGS - NO NEED BABY
# TODO LIST
# GET RID OF COOKIES

def main_crawler(url:str, course_name:str, max_urls:int=100, max_depth:int=3, timeout:int=1):
  max_urls = int(max_urls)
  max_depth = int(max_depth)
  timeout = int(timeout)
  data = crawler(url, max_urls, max_depth, timeout)

  print("Crawl Success!")
  print("Begin Ingest")

  ingester = Ingest()
  s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    )
  print(len(data))

  # Clean some keys for a proper file name
  titles = [value[1][1].title.string for value in data]
  clean = [re.match(r"[a-zA-Z0-9\s]*", title).group(0) for title in titles]
  path_name = []
  counter = 0
  for value in clean:
    value = value.strip()
    value = value.replace(" ", "_")
    if value == "403_Forbidden":
      print("Found Forbidden Key, deleting data")
      del data[counter]
    else:
      path_name.append(value)
      counter += 1

  # Upload each html to S3
  print("Uploading", len(data), "files to S3")
  paths = []
  for i, key in enumerate(data):
    with NamedTemporaryFile(suffix=".html") as temp_html:
      temp_html.write(key[1][1].encode('utf-8'))
      temp_html.seek(0)
      s3_upload_path = "courses/"+ course_name + "/" + path_name[i] + ".html"
      paths.append(s3_upload_path)
      with open(temp_html.name, 'rb') as f:
        print("Uploading html to S3")
        s3_client.upload_fileobj(f, os.getenv('S3_BUCKET_NAME'), s3_upload_path)

    if key[1][2] != []:
      with NamedTemporaryFile(suffix=".pdf") as temp_pdf:
        for pdf in key[1][2]:
          temp_pdf.write(pdf)
          temp_pdf.seek(0) 
          s3_upload_path = "courses/"+ course_name + "/" + path_name[i] + ".pdf"
          paths.append(s3_upload_path)
          with open(temp_pdf.name, 'rb') as f:
            print("Uploading html to S3")
            s3_client.upload_fileobj(f, os.getenv('S3_BUCKET_NAME'), s3_upload_path)

  print("Begin Ingest")
  success_fail_dict = ingester.bulk_ingest(paths, course_name, clean_text=data)

  return success_fail_dict