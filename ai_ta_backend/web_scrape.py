import os
import re
import shutil
import time
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

import boto3  # type: ignore
import requests
from bs4 import BeautifulSoup

import supabase

from ai_ta_backend.aws import upload_data_files_to_s3
from ai_ta_backend.vector_database import Ingest
import mimetypes

def get_file_extension(filename):
    match = re.search(r'\.([a-zA-Z0-9]+)$', filename)
    valid_filetypes = list(mimetypes.types_map.keys())
    valid_filetypes = valid_filetypes + ['.html', '.py', '.vtt', '.pdf', '.txt', '.srt', '.docx', '.ppt', '.pptx']
    if match:
        filetype = "." + match.group(1)
        if filetype in valid_filetypes:
            return filetype
        else:
            return '.html'
    else:
        return '.html'

def valid_url(url):
  '''Returns the URL and it's content if it's good, otherwise returns false. Prints the status code.'''
  try:
    response = requests.get(url, allow_redirects=True, timeout=20)

    redirect_loop_counter = 0
    while response.status_code == 301:
      # Check for permanent redirect
      if redirect_loop_counter > 3:
        print("❌ Redirect loop (on 301 error) exceeded redirect limit of:", redirect_loop_counter, "❌")
        return False
      redirect_url = response.headers['Location']
      response = requests.head(redirect_url)
      redirect_loop_counter += 1
    if response.status_code == 200:
      filetype = get_file_extension(response.url)
      print("file extension:", filetype)
      if filetype == '.html':
        content = BeautifulSoup(response.content, "html.parser")
        if "<!doctype html" not in str(response.text).lower():
          print("⛔️⛔️ Filetype not supported:", response.url, "⛔️⛔️")
          return (False, False, False)
      elif filetype in ['.py', '.vtt', '.pdf', '.txt', '.srt', '.docx', '.ppt', '.pptx']:
        if "<!doctype html" in str(response.text).lower():
          content = BeautifulSoup(response.text, "html.parser")
          filetype = '.html'
        else:
          content = response.content
      else:
        return (False, False, False)
      if filetype not in ['.html', '.py', '.vtt', '.pdf', '.txt', '.srt', '.docx', '.ppt', '.pptx']:
        print("Filetype not supported:", filetype)
      return (response.url, content, filetype)
    else:
      print("🚫🚫 URL is invalid:", response.url, "Return code:", response.status_code, "🚫🚫")
      return (False, False, False)
  except requests.RequestException as e:
    print("🚫🚫 URL is invalid:", url, "Error:", e, "🚫🚫")
    return (False, False, False)

# Ensures url is in the correct format
def base_url(url:str):
  try:
    # Get rid of double slashes in url
    # Create a base site for incomplete hrefs
    if url.startswith("https:"):
      site= re.match(pattern=r'https:\/\/[a-zA-Z0-9.]*[a-z]', string=url).group(0) # type: ignore
      url = re.sub(pattern=r"https:\/\/", repl="", string=url)
      url = re.sub(pattern=r"[\/\/]{2,}", repl="", string=url)
      url = "https://"+url
      return site
    elif url.startswith("http:"):
      site = re.match(pattern=r'http:\/\/[a-zA-Z0-9.]*[a-z]', string=url).group(0) # type: ignore
      url = re.sub(pattern=r"http:\/\/", repl="", string=url)
      url = re.sub(pattern=r"[\/\/]{2,}", repl="", string=url)
      url = "http://"+url
      return site
    else:
      return []
  except Exception as e:
    print("Error:", e)
    return []

def find_urls(soup:BeautifulSoup, urls:set, site:str):
  try:
    for i in soup.find_all("a"): # type: ignore
      try:
      # getting the href tag
        href = i.attrs['href']
      except KeyError as e:
        print("KeyError:", e, "for", i)
        continue

      # decipher type of href
      if href.startswith("http"):
        pass
      elif href.startswith("/"):
        href = site+href
      else:
        href = site+'/'+href
      urls.add(href)

  except Exception as e:
    print("Error in body:", e)
    pass

  return urls

def remove_duplicates(urls:list, supabase_urls:list=None):
# Delete repeated sites, with different URLs and keeping one
  # Making sure we don't have duplicate urls from Supabase
  if supabase_urls:
    supa_urls = [url[0] for url in supabase_urls]
    supa_content = [url[1] for url in supabase_urls]
    print("supa_urls", supa_urls)
  else:
    print("No supabase urls")

  og_len = len(urls)
  
  if supabase_urls:
    for row in urls:
      if row[2] == '.html':
        if row[1].get_text() in supa_content:
          urls.remove(row)
          print("❌ Removed", row[0], "from urls because it is in supa ❌")
      else:
        if row[0] in supa_urls:
          urls.remove(row)
          print("❌ Removed", row[0], "from urls because it is in supa ❌")

  not_repeated_files = []
  print("deleting duplicate files")
  for row in urls:
    if row[1] not in not_repeated_files:
      not_repeated_files.append(row[1])
    else:
      urls.remove(row)
      print("❌ Removed", row[0], "from urls because it is a duplicate ❌")
      continue
  print("deleted", og_len-len(not_repeated_files), "duplicate files")
  return urls

def crawler(url:str, max_urls:int=1000, max_depth:int=3, timeout:int=1, base_url_on:str=None, _depth:int=0, _soup:BeautifulSoup=None, _filetype:str=None,  _invalid_urls:list=[], _existing_urls:list=None):
  '''Function gets titles of urls and the urls themselves'''
  # Prints the depth of the current search
  print("depth: ", _depth)
  url_contents = []
  max_urls = int(max_urls)
  _depth = int(_depth)
  max_depth = int(max_depth)
  if base_url_on:
    base_url_on = str(base_url_on)

  amount = max_urls
  
  # Get rid of double slashes in url
  # Create a base site for incomplete hrefs
  base = base_url(url)
  if base ==[]:
    return []
  else:
    site = base

  urls= set()

  if _soup:
    s = _soup
    filetype = _filetype
  else:
    url, s, filetype = valid_url(url)
    time.sleep(timeout)
    url_contents.append((url,s, filetype))
    print("Scraped:", url)
  if url: 
    if filetype == '.html':
      try:
        body = s.find("body")
        header = s.find("head") 
      except Exception as e:
        print("Error:", e)
        body = ""
        header = ""

      # Check for 403 Forbidden urls
      try:
        if s.title.string.lower() == "403 forbidden" or s.title.string.lower() == 'page not found': # type: ignore
          print("403 Forbidden")
        else:
          pass
      except Exception as e:
        print("Error:", e)
        pass 
      if body != "" and header != "":
        urls = find_urls(body, urls, site)
        urls = find_urls(header, urls, site)
      else:
        urls = find_urls(s, urls, site)
    else:
      pass
  else:
    _invalid_urls.append(url)
    return []

  urls = list(urls)
  if max_urls > len(urls):
    max_urls = max_urls - len(urls)
  elif max_urls < len(urls):
    urls = urls[:max_urls]
    max_urls = 0
  else:
    max_urls = 0
  # We grab content out of these urls

  for url in urls:
    if base_url_on:
      if url.startswith(site):
        url, s, filetype = valid_url(url)
        if url:
          print("Scraped:", url)
          url_contents.append((url, s, filetype))
        else:
          _invalid_urls.append(url)
      else:
        pass
    else:
      url, s, filetype = valid_url(url)
      if url:
        print("Scraped:", url)
        url_contents.append((url, s, filetype))
      else:
        _invalid_urls.append(url)
  
  url_contents = remove_duplicates(url_contents, _existing_urls)
  max_urls = max_urls - len(url_contents)
  print(max_urls, "urls left")

  # recursively go through crawler until we reach the max amount of urls. 
  for url in url_contents:
    if url[0] not in _invalid_urls:
      if max_urls > 0:
        if _depth < max_depth:
          temp_data = crawler(url[0], max_urls, max_depth, timeout, _invalid_urls, _depth, url[1], url[2])
          temp_data = remove_duplicates(temp_data, _existing_urls)
          max_urls = max_urls - len(temp_data)
          print(max_urls, "urls left")
          url_contents.extend(temp_data)
          url_contents = remove_duplicates(url_contents, _existing_urls)
        else:
          print("Depth exceeded:", _depth+1, "out of", max_depth)
          break
      else:
        break
    else:
      pass
  
  if _depth == 0:
    if len(url_contents) < amount:
      print("Max URLS not reached, returning all urls found:", len(url_contents), "out of", amount)
    elif len(url_contents) == amount:
      print("Max URLS reached:", len(url_contents), "out of", amount)
    else:
      print("Exceeded Max URLS, found:", len(url_contents), "out of", amount)
  print(len(url_contents), "urls found")
  return url_contents

def is_github_repo(url):
    pattern = re.compile(r'^https://github\.com/[^/]+/[^/]+$')
    if not pattern.match(url):
      return False

    response = requests.head(url)
    if response.status_code == 200 and response.headers['Content-Type'].startswith('text/html'):
      return url
    else:
      return False

def main_crawler(url:str, course_name:str, max_urls:int=100, max_depth:int=3, timeout:int=1, stay_on_baseurl:bool=False):
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
  stay_on_baseurl = bool(stay_on_baseurl)
  if stay_on_baseurl:
    stay_on_baseurl = base_url(url)
    print(stay_on_baseurl)

  ingester = Ingest()
  s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    )

  # Check for GitHub repository coming soon
  if is_github_repo(url):
    print("Begin Ingesting GitHub page")
    results = ingester.ingest_github(url, course_name)
    print("Finished ingesting GitHub page")
    return results
  else:
    print("Gathering existing urls from Supabase")
    supabase_client = supabase.create_client(  # type: ignore
    supabase_url=os.getenv('SUPABASE_URL'),  # type: ignore
    supabase_key=os.getenv('SUPABASE_API_KEY'))  # type: ignore
    urls = supabase_client.table(os.getenv('NEW_NEW_NEWNEW_MATERIALS_SUPABASE_TABLE')).select('course_name, url, contexts').eq('course_name', course_name).execute()
    if urls.data == []:
      existing_urls = None
    else:
      existing_urls = []
      for thing in urls.data:
        whole = ''
        for t in thing['contexts']:
          whole += t['text']
        existing_urls.append((thing['url'], whole))
    print("Finished gathering existing urls from Supabase")
    print("Begin Ingesting Web page")
    data = crawler(url=url, max_urls=max_urls, max_depth=max_depth, timeout=timeout, base_url_on=stay_on_baseurl, _existing_urls=existing_urls)

  # Clean some keys for a proper file name
  # todo: have a default title
  # titles = [value[1][1].title.string for value in data]

  titles = []
  for value in data:
    try:
      titles.append(value[1].title.string)  
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
  try:
    for i, key in enumerate(data):
      with NamedTemporaryFile(suffix=key[2]) as temp_file:
          if key[1] != "" or key[1] != None:
            if key[2] == ".html":
              print("Writing", key[2] ,"to temp file")
              temp_file.write(key[1].encode('utf-8'))
            else:
              print("Writing", key[2] ,"to temp file")
              temp_file.write(key[1])
            temp_file.seek(0)
            s3_upload_path = "courses/"+ course_name + "/" + path_name[i] + key[2]
            paths.append(s3_upload_path)
            with open(temp_file.name, 'rb') as f:
              print("Uploading", key[2] ,"to S3")
              s3_client.upload_fileobj(f, os.getenv('S3_BUCKET_NAME'), s3_upload_path)
              ingester.bulk_ingest(s3_upload_path, course_name=course_name, url=key[0], base_url=url)
              counter += 1
          else:
            print("No", key[2] ,"to upload", key[1])
      # if ".pdf" in key[0]:
      #   with NamedTemporaryFile(suffix=".pdf") as temp_pdf:
      #     if key[1] != "" or key[1] != None:
      #       temp_pdf.write(key[1])
      #       temp_pdf.seek(0)
      #       s3_upload_path = "courses/"+ course_name + "/" + path_name[i] + ".pdf"
      #       paths.append(s3_upload_path)
      #       with open(temp_pdf.name, 'rb') as f:
      #         print("Uploading PDF to S3")
      #         s3_client.upload_fileobj(f, os.getenv('S3_BUCKET_NAME'), s3_upload_path)
      #         ingester.bulk_ingest(s3_upload_path, course_name=course_name, url=key[0], base_url=url)
      #         counter += 1
      #     else:
      #       print("No PDF to upload", key[1])
      # else:
      #   with NamedTemporaryFile(suffix=".html") as temp_html:
      #     if key[1] != "" or key[1] != None:
      #       temp_html.write(key[1].encode('utf-8'))
      #       temp_html.seek(0)
      #       s3_upload_path = "courses/"+ course_name + "/" + path_name[i] + ".html"
      #       paths.append(s3_upload_path)
      #       with open(temp_html.name, 'rb') as f:
      #         print("Uploading html to S3")
      #         s3_client.upload_fileobj(f, os.getenv('S3_BUCKET_NAME'), s3_upload_path)
      #         ingester.bulk_ingest(s3_upload_path, course_name=course_name, url=key[0], base_url=url)
      #         counter += 1
      #     else:
      #       print("No html to upload", key[1])
  except Exception as e:
    print("Error in upload:", e)

  print("Successfully uploaded", counter, "files to S3")
  print("Finished /web-scrape")

# Download an MIT course using its url
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

