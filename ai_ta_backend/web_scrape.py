import os
import re
import shutil
import time
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

import boto3  # type: ignore
import requests
from bs4 import BeautifulSoup

from ai_ta_backend.aws import upload_data_files_to_s3
from ai_ta_backend.vector_database import Ingest


def valid_url(url):
  '''Returns the URL if it's good, otherwise returns false. Prints the status code.'''
  try:
    response = requests.head(url, allow_redirects=True)
    
    redirect_loop_counter = 0
    while response.status_code == 301:
      # Check for permanent redirect
      if redirect_loop_counter > 3:
        print("Redirect loop (on 301 error) exceeded redirect limit of:", redirect_loop_counter)
        return False
      redirect_url = response.headers['Location']
      response = requests.head(redirect_url)
      redirect_loop_counter += 1
    
    if response.status_code == 200:
      return response.url
    else:
      print("URL is invalid:", response.url, "Return code:", response.status_code)
      return False
  except requests.RequestException as e:
    print("URL is invalid:", url, "Error:", e)
    return False

def get_urls_list(url:str):
    '''Function gets titles of urls and the urls themselves'''
    # Get rid of double slashes in url
    # Create a base site for incomplete hrefs

    try:
      if url.startswith("https:"):
        site= re.match(pattern=r'https:\/\/[a-zA-Z0-9.]*[a-z]', string=url).group(0) # type: ignore
        url = re.sub(pattern=r"https:\/\/", repl="", string=url)
        url = re.sub(pattern=r"[\/\/]{2,}", repl="", string=url)
        url = "https://"+url
      elif url.startswith("http:"):
        site = re.match(pattern=r'http:\/\/[a-zA-Z0-9.]*[a-z]', string=url).group(0) # type: ignore
        url = re.sub(pattern=r"http:\/\/", repl="", string=url)
        url = re.sub(pattern=r"[\/\/]{2,}", repl="", string=url)
        url = "http://"+url
      else:
        return []
    except Exception as e:
      print("Error:", e)
      return []

    urls= set()

    r = requests.get(url)
    s = BeautifulSoup(r.text,"html.parser")
    body = s.find("body")
    header = s.find("head") 
    try:
        if s.title.string == "403 Forbidden": # type: ignore
            print("403 Forbidden")
        else:
            pass
    except Exception as e:
        print("Error:", e)
        pass 
    
    # header = s.find("head")
    for i in body.find_all("a"): # type: ignore
        try:
        # getting the href tag
            href = i.attrs['href']
        except KeyError as e:
            print("KeyError:", e, "for", i)
            continue
    
        if href.startswith("http"):
            pass
        elif href.startswith("/"):
            href = site+href
        else:
            href = site+'/'+href
        urls.add(href)

    for i in header.find_all("a"): # type: ignore
        try:
        # getting the href tag
            href = i.attrs['href']
        except KeyError as e:
            print("KeyError:", e, "for", i)
            continue
    
        if href.startswith("http"):
            pass
        elif href.startswith("/"):
            href = site+href
        else:
            href = site+'/'+href
        urls.add(href)

    return list(urls)


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
  valid_base_url = valid_url(base_url)
  if valid_base_url:
    base_url = valid_base_url
    all.append(base_url)
    urls = get_urls_list(base_url)

    if len(urls) <= max_urls:
      all.extend(urls)
    else:
      all.extend(urls[:max_urls])
  else:
    _invalid_urls.append(base_url)

  # Create the new amount of max urls for the next function call
  all = list(set(all))
  max_urls = max_urls - len(all)

  # Recursively call the function on all of the urls found in the base url
  for url in all:
    # if url.startswith(base_url):
      # _invalid_urls.append(url)
      if url not in _invalid_urls:
        valid_url_result = valid_url(url)
        if valid_url_result:
          url = valid_url_result
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


def pdf_scraper(soup:BeautifulSoup, url:str): 
  try:
    if url.startswith("https:"):
      base= re.match(pattern=r'https:\/\/[a-zA-Z0-9.]*[a-z]', string=url).group(0) # type: ignore
    elif url.startswith("http:"):
      base = re.match(pattern=r'http:\/\/[a-zA-Z0-9.]*[a-z]', string=url).group(0) # type: ignore
    else:
      return []
  except Exception as e:
    print("Error:", e)
    return []
  
  links = soup.find_all('a')
  pdf = []
  try:
    for link in links:
      if ('.pdf' in link.get('href', [])):
        # Get response object for link
        if link.get('href').startswith("http"):
          site = link.get('href')
        elif link.get('href').startswith("/"):
          site = base+link.get('href')
        else:
          site = base+'/'+link.get('href')
        response = requests.get(site)
        content =  response.content
        if f"<!DOCTYPE html>" not in str(content):
          pdf.append(content)
          print("PDF scraped:", site)
  except Exception as e:
    print("PDF scrape error:", e)

  return list(set(pdf))


def crawler(site:str, max_urls:int=1000, max_depth:int=3, timeout:int=1):
    """
    Crawl a site and scrape its content and PDFs.

    Args:
        site (str): The URL of the site to crawl.
        max_urls (int, optional): The maximum number of URLs to crawl. Defaults to 1000.
        max_depth (int, optional): The maximum depth of URLs to crawl. Defaults to 3.
        timeout (int, optional): The number of seconds to wait between requests. Defaults to 1.

    Returns:
        A list of lists, where each inner list contains the URL, text content, BeautifulSoup object, and list of PDF URLs for a crawled site.
    """
    all_sites = list(set(site_map(site, max_urls, max_depth)))
    crawled = []
    invalid_urls = []

    for site in all_sites:
        try:
            soup = scraper(site)
            site_data = []
            site_data.append(site)
            site_data.append(soup.get_text())
            site_data.append(soup)
            print("Scraped:", site)
            site_data.append(pdf_scraper(soup, site))
            crawled.append(site_data)
            time.sleep(timeout)

        except Exception as e:
            print("Url Not Scraped!!!", "Exception:", e)
            invalid_urls.append(site)
            continue
        
    # Delete repeated sites, with different URLs and keeping one
    repeated = [value[2] for value in crawled]
    counts = {value:repeated.count(value) for value in repeated}
  
    for value in repeated:
        for i, row in enumerate(crawled):
            if counts[value] > 1:
                if row[2] == value:
                  counts[value] -= 1
                  del crawled[i]
            else:
                break
              
    # Delete repeated PDFs and keeping one

    pdf_repeat = []
    for value in crawled:
        pdf_repeat.extend(value[3])
    pdf_counts = {value:pdf_repeat.count(value) for value in pdf_repeat}

    for value in pdf_repeat:
        for row in crawled:
            count = row[3].count(value)
            if pdf_counts[value] == 1:
                break
            elif pdf_counts[value] > count:
                for i in range(count):
                    row[3].remove(value)
                    pdf_counts[value] -= 1
            else:
                for i in range(pdf_counts[value]-1):
                    row[3].remove(value)
                    pdf_counts[value] -= 1

    # IF we need pdf to be dictionary and want the pdf urls as well. 
    # pdf_repeat = [value[3].values() for value in crawled]
    # counts = {value:pdf_repeat.count(value) for value in pdf_repeat}

    # for row in crawled:
    #   for key, value in row[3].items():
    #     if counts[value] > 1:
    #       counts[value] -= 1
    #       del row[3][key]
    #     else:
    #       break

    print("Scraped", len(crawled), "urls out of", max_urls)

    return crawled

# Download a course using its url
def mit_course_download(url:str, course_name:str, local_dir:str):
    ingester = Ingest()
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

    zip_file = local_dir + ".zip"

    try:
        with open(zip_file, 'wb') as fd:
            for chunk in r.iter_content(chunk_size=128):
                fd.write(chunk)
        print("course downloaded!")
    except Exception as e:
        print("Error:", e, site)

    with ZipFile(zip_file, 'r') as zObject:
      zObject.extractall(
        path=local_dir)
    
    shutil.move(local_dir+"/"+"robots.txt", local_dir+"/static_resources")
    s3_paths = upload_data_files_to_s3(course_name, local_dir+"/static_resources")
    success_fail = ingester.bulk_ingest(s3_paths, course_name) # type: ignore

    shutil.move(zip_file, local_dir)
    shutil.rmtree(local_dir)
    print("Finished Ingest")
    return success_fail

def main_crawler(url:str, course_name:str, max_urls:int=100, max_depth:int=3, timeout:int=1):
  """
  Crawl a site and scrape its content and PDFs, then upload the data to S3 and ingest it.

  Args:
    url (str): The URL of the site to crawl.
    course_name (str): The name of the course to associate with the crawled data.
    max_urls (int, optional): The maximum number of URLs to crawl. Defaults to 100.
    max_depth (int, optional): The maximum depth of URLs to crawl. Defaults to 3.
    timeout (int, optional): The number of seconds to wait between requests. Defaults to 1.

  Returns:
    None
  """
  print("\n")
  max_urls = int(max_urls)
  max_depth = int(max_depth)
  timeout = int(timeout)
  data = crawler(url, max_urls, max_depth, timeout)

  print("Begin Ingest")

  ingester = Ingest()
  s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    )
  # Clean some keys for a proper file name
  # todo: have a default title
  # titles = [value[1][1].title.string for value in data]

  titles = []
  for value in data:
    try:
      titles.append(value[2].title.string)  
    except AttributeError as e:
      # if no title
      try:
        placeholder_title = re.findall(pattern=r'[a-zA-Z0-9.]*[a-z]', string=value[0])[1]
      except Exception as e:
        placeholder_title = "Title Not Found"
      titles.append(placeholder_title)
      print(f"URL is missing a title, using this title instead: {placeholder_title}")

  try:
    clean = [re.match(r"[a-zA-Z0-9\s]*", title).group(0) for title in titles] # type: ignore
  except Exception as e:
    print("Error:", e)
    clean = titles
  print("title names after regex before cleaning", clean)
  path_name = []
  counter = 0
  for value in clean:
    value = value.strip() if value else ""
    # value = value.strip()
    value = value.replace(" ", "_")
    if value == "403_Forbidden":
      print("Found Forbidden Key, deleting data")
      del data[counter]
    else:
      path_name.append(value)
      counter += 1
      
  print("Cleaned title names", path_name)


  # Upload each html to S3
  print("Uploading files to S3")
  paths = []
  counter = 0
  for i, key in enumerate(data):
    with NamedTemporaryFile(suffix=".html") as temp_html:
      temp_html.write(key[2].encode('utf-8'))
      temp_html.seek(0)
      s3_upload_path = "courses/"+ course_name + "/" + path_name[i] + ".html"
      paths.append(s3_upload_path)
      with open(temp_html.name, 'rb') as f:
        print("Uploading html to S3")
        s3_client.upload_fileobj(f, os.getenv('S3_BUCKET_NAME'), s3_upload_path)
        ingester.bulk_ingest(s3_upload_path, course_name=course_name, url=key[0])
        counter += 1

    if key[3] != []:
      with NamedTemporaryFile(suffix=".pdf") as temp_pdf:
        for pdf in key[3]:
          temp_pdf.write(pdf)
          temp_pdf.seek(0) 
          s3_upload_path = "courses/"+ course_name + "/" + path_name[i] + ".pdf"
          paths.append(s3_upload_path)
          with open(temp_pdf.name, 'rb') as f:
            print("Uploading PDF to S3")
            s3_client.upload_fileobj(f, os.getenv('S3_BUCKET_NAME'), s3_upload_path)
            ingester.bulk_ingest(s3_upload_path, course_name)
            counter += 1

  print("Successfully uploaded", counter, "files to S3")
  print("Finished /web-scrape")
