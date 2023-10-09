import mimetypes
import os
import re
import shutil
import time
from collections import Counter
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

import boto3  # type: ignore
import requests
import supabase
from bs4 import BeautifulSoup

from ai_ta_backend.aws import upload_data_files_to_s3
from ai_ta_backend.vector_database import Ingest


class WebScrape():

  def __init__(self) -> None:
    
    # S3
    self.s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    )

    # Create a Supabase client
    self.supabase_client = supabase.create_client(  # type: ignore
        supabase_url=os.environ['SUPABASE_URL'],
        supabase_key=os.environ['SUPABASE_API_KEY'])
    
    self.ingester = Ingest()
    
    self.url_contents = []
    self.invalid_urls = []
    self.existing_urls = []
    self.max_urls = 0
    self.original_amount = 0
    self.supa_urls = 0
    self.queue = {}

    return None

  def get_file_extension(self, filename):
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

  def valid_url(self, url):
    '''Returns the URL and it's content if it's good, otherwise returns false. Prints the status code.'''
    try:
      response = requests.get(url, allow_redirects=True, timeout=20)

      redirect_loop_counter = 0
      while response.status_code == 301:
        # Check for permanent redirect
        if redirect_loop_counter > 3:
          print("❌ Redirect loop (on 301 error) exceeded redirect limit of:", redirect_loop_counter, "❌")
          return (False, False, False)
        redirect_url = response.headers['Location']
        response = requests.head(redirect_url)
        redirect_loop_counter += 1
      if response.status_code == 200:
        filetype = self.get_file_extension(response.url)
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
          print("⛔️⛔️ Filetype not supported:", filetype, "⛔️⛔️")
          return (False, False, False)
        return (response.url, content, filetype)
      else:
        print("🚫🚫 URL is invalid:", response.url, "Return code:", response.status_code, "🚫🚫")
        return (False, False, False)
    except requests.RequestException as e:
      print("🚫🚫 URL is invalid:", url, "Error:", e, "🚫🚫")
      return (False, False, False)

  # Ensures url is in the correct format
  def base_url(self, url:str):
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
        return ""
    except Exception as e:
      print("Error:", e)
      return ""

  def find_urls(self, soup:BeautifulSoup, site:str, urls:list):
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
        urls.append(href)

    except Exception as e:
      print("Error in body:", e)
      pass

    return urls

  def title_path_name(self, value):
    try:
      title = value[1].title.string
    except AttributeError as e:
      # if no title
      try:
        title = re.findall(pattern=r'[a-zA-Z0-9.]*[a-z]', string=value[0])[1]
      except Exception as e:
        title = "Title Not Found"
      print(f"URL is missing a title, using this title instead: {title}")

    try:
      clean = re.match(r"[a-zA-Z0-9\s]*", title).group(0) # type: ignore
    except Exception as e:
      print("Error:", e)
      clean = title
    print("title names after regex before cleaning", clean)
    if clean: 
      clean = clean.strip() 
    else:
      clean = ""
    clean = clean.replace(" ", "_")
    if clean == "403_Forbidden" or clean == "Page_Not_Found":
      print("Found Forbidden Key, deleting data")
      return None
    else:
      print("Cleaned title name:", clean)
      return clean

  def ingest_file(self, key, course_name, path_name, base_url):
    try:
      with NamedTemporaryFile(suffix=key[2]) as temp_file:
          if key[1] != "" or key[1] != None:
            if key[2] == ".html":
              print("Writing", key[2] ,"to temp file")
              temp_file.write(key[1].encode('utf-8'))
            else:
              print("Writing", key[2] ,"to temp file")
              temp_file.write(key[1])
            temp_file.seek(0)
            s3_upload_path = "courses/"+ course_name + "/" + path_name + key[2]
            with open(temp_file.name, 'rb') as f:
              print("Uploading", key[2] ,"to S3")
              self.s3_client.upload_fileobj(f, os.getenv('S3_BUCKET_NAME'), s3_upload_path)
              self.ingester.bulk_ingest(s3_upload_path, course_name=course_name, url=key[0], base_url=base_url)
          else:
            print("No", key[2] ,"to upload", key[1])
    except Exception as e:
      print("Error in upload:", e)

  # def remove_duplicates(urls:list=[], _existing_urls:list=[]):
  # # Delete repeated sites, with different URLs and keeping one
  #   # Making sure we don't have duplicate urls from Supabase
  #   og_len = len(urls)
  #   existing_files = [url[1] for url in _existing_urls if url!=False]
  #   existing_urls = [url[0] for url in _existing_urls if url!=False]

  #   if urls: 
  #     print("deleting duplicate files")
  #     for row in urls:
  #       if row[0] in existing_urls:
  #         urls.remove(row)
  #         print("❌ Removed", row[0], "from urls because it is a duplicate ❌")
  #         continue
  #       elif row[1] in existing_files:
  #         urls.remove(row)
  #         print("❌ Removed", row[0], "from urls because it is a duplicate ❌")
  #         continue
  #       else:
  #         existing_urls.append(row[0])
  #         existing_files.append(row[1])
  #     print("deleted", og_len-len(urls), "duplicate files")
  #   else:
  #     print("No urls to delete")

  #   return urls

  def check_file_not_exists(self, file):
    contents = [url[1] for url in self.existing_urls]
    urls = [url[0] for url in self.existing_urls]
    if file[1] in contents or file[0] in urls:
      return False
    else:
      return True
  
  # # Counts the average number of repeated urls and if it is too high, it will exit the web scraper
  # def count_hard_stop_avg(self, average:int=4):
  #   # Counts the number of repeated urls and if it is too high, it will exit the web scraper
  #   all_urls = self.existing_urls + self.invalid_urls
  #   counted_urls = Counter(all_urls)
  #   if len(counted_urls) != 0:
  #     print(counted_urls[False], "False stuff")
  #     print("📈📈 Counted URLs", sum(counted_urls.values())/len(counted_urls), "📈📈")
  #     if sum(counted_urls.values())/len(counted_urls) > average:
  #       print("Too many repeated urls, exiting web scraper")
  #       return True
  #     else:
  #       return False

  def count_hard_stop_len(self):
    count = len(self.url_contents)
    if self.url_contents != []:
      print("📈📈 Counted URLs", count, "out of", self.original_amount, "📈📈" )
      if count > self.original_amount:
        print("Too many repeated urls, exiting web scraper")
        return True
      else:
        return False

  def remove_falses(self):
    for url in self.url_contents:
      if url == False or url == True or type(url) != tuple:
        self.url_contents.remove(url)
    return None


  def check_and_ingest(self, url:str, course_name:str, timeout:int, base_url_on:str):
    if url not in self.invalid_urls and url not in self.existing_urls:
      second_url, content, filetype = self.valid_url(url)
    else:
      print("This URL is invalid or already existing in the database")
      self.existing_urls.append((url))
      return '', '', ''
    
    if second_url:
      time.sleep(timeout)
      url_content = (second_url, content, filetype)
      if self.check_file_not_exists(url_content):
        path_name = self.title_path_name(url_content)
        self.url_contents.append(url_content)
        self.existing_urls.append(url_content)
        # url_contents = remove_duplicates(url_contents, _existing_urls)
        self.ingest_file(url_content, course_name, path_name, base_url_on)
        print("✅✅ Scraped:", second_url, "✅✅")
        self.max_urls -= 1
      else:
        print("This URL is already existing in the database")
        self.existing_urls.append((second_url, content, filetype))
    else:
      self.invalid_urls.append(url)
      print("This URL is invalid")
    
    return url, content, filetype

  def scrape_user_provided_page(self, url:str, course_name:str, timeout:int, base:str):
    urls= []
    url, content, filetype = self.check_and_ingest(url, course_name, timeout, base)

    if url:
      if filetype == '.html':
        try:
          body = content.find("body")
          header = content.find("head") 
        except Exception as e:
          print("Error:", e)
          body = ""
          header = ""
        # Check for 403 Forbidden urls
        try:
          if content.title.string.lower() == "403 forbidden" or content.title.string.lower() == 'page not found': # type: ignore
            print("403 Forbidden")
            self.invalid_urls.append(url)
          else:
            pass
        except Exception as e:
          print("Error:", e)
          pass 
        if body != "" and header != "":
          urls = self.find_urls(body, base, urls) # type: ignore
          urls = self.find_urls(header, base, urls)# type: ignore
        else:
          urls = self.find_urls(content, base, urls)# type: ignore

    return urls
  
  def non_user_provided_page_urls(self, url:str, base:str, soup, filetype:str):
    urls = []
    if filetype == '.html':
      try:
        body = soup.find("body")
        header = soup.find("head") 
      except Exception as e:
        print("Error:", e)
        body = ""
        header = ""

      # Check for 403 Forbidden urls
      try:
        if soup.title.string.lower() == "403 forbidden" or soup.title.string.lower() == 'page not found': # type: ignore
          print("403 Forbidden")
          self.invalid_urls.append(url)
        else:
          pass
      except Exception as e:
        print("Error:", e)
        pass 
      if body != "" and header != "":
        urls = self.find_urls(body, base, urls)
        urls = self.find_urls(header, base, urls)
      else:
        urls = self.find_urls(soup, base, urls)
    
    return urls

  def depth_crawler(self, url:str, course_name:str, max_depth:int=3, timeout:int=1, base_url_on:str=None, _depth:int=0, _soup=None, _filetype:str=None): # type: ignore
    '''Function gets titles of urls and the urls themselves'''
    # Prints the depth of the current search
    print("depth: ", _depth)
    if base_url_on:
      base_url_on = str(base_url_on)
    
    # Create a base site for incomplete hrefs
    base = self.base_url(url)
    if base == "":
      raise ValueError("This URL is invalid")
    
    if self.count_hard_stop_len():
      raise ValueError("Too many repeated urls, exiting web scraper")
    
    try:
      if _soup:
        urls = self.non_user_provided_page_urls(url, base, _soup, _filetype)
      else:
        urls = self.scrape_user_provided_page(url, course_name, timeout, base)
    except ValueError as e:
      raise e
    
    temp_urls = []
    # We grab content out of these urls
    try:
      for url in urls:
        if self.max_urls > 0:
          if base_url_on:
            if url.startswith(base):
              new_url, content, filetype = self.check_and_ingest(url, course_name, timeout, base_url_on)
              if new_url:
                temp_urls.append((new_url, content, filetype))
              if self.count_hard_stop_len():
                raise ValueError("Too many repeated urls, exiting web scraper")
          else:
            new_url, content, filetype = self.check_and_ingest(url, course_name, timeout, base_url_on)
            if new_url:
              temp_urls.append((new_url, content, filetype))
            if self.count_hard_stop_len():
              raise ValueError("Too many repeated urls, exiting web scraper")     
        else:
          print("Max URLs reached")
          raise ValueError("Max URLs reached")
    except ValueError as e:
      print("Error:", e)
    
    # recursively go through crawler until we reach the max amount of urls. 
    for url in temp_urls:
      if self.max_urls > 0:
        if _depth < max_depth:
          self.depth_crawler(url[0], course_name, max_depth, timeout, base_url_on, _depth+1, url[1], url[2])
          print(self.max_urls, "urls left")
          if self.count_hard_stop_len():
            raise ValueError("Too many repeated urls, exiting web scraper")
        else:
          print("Depth exceeded:", _depth+1, "out of", max_depth)
          break
      else:
        print("Max urls reached") 
        break
  
    return None
  
  def breadth_crawler(self, url:str, course_name:str, timeout:int=1, base_url_on:str=None, max_depth:int=3): # type: ignore
    depth = 1
    if base_url_on:
      base_url_on = str(base_url_on)
    
    # Create a base site for incomplete hrefs
    base = self.base_url(url)
    if base == "":
      raise ValueError("This URL is invalid")
    
    self.queue[depth] = self.scrape_user_provided_page(url, course_name, timeout,  base)
    self.queue[depth+1] = []
    print("queue", self.queue)
    print("len", len(self.queue[depth]), len(self.queue[depth+1]))
    
    while self.count_hard_stop_len() == False:
      print("queue", len(self.queue[depth]), len(self.queue[depth+1]))

      if self.queue[depth] == []:
        depth += 1
        print("depth:", depth)
        self.queue[depth+1] = []
        if depth > max_depth:
          print("Depth exceeded:", depth, "out of", max_depth)
          raise ValueError("Depth exceeded")

      url = self.queue[depth].pop(0)
      print(url)
      if self.max_urls > 0:
        if depth <= max_depth:
          if base_url_on:
            if url.startswith(base):
              new_url, content, filetype = self.check_and_ingest(url, course_name, timeout, base_url_on)
              self.queue[depth+1] += self.non_user_provided_page_urls(new_url, base, content, filetype)
              if self.count_hard_stop_len():
                raise ValueError("Too many repeated urls, exiting web scraper")
            else:
              new_url, content, filetype = self.check_and_ingest(url, course_name, timeout, base_url_on)
              if self.count_hard_stop_len():
                raise ValueError("Too many repeated urls, exiting web scraper")
          else:
            new_url, content, filetype = self.check_and_ingest(url, course_name, timeout, base_url_on)
            self.queue[depth+1] += self.non_user_provided_page_urls(new_url, base, content, filetype)
            if self.count_hard_stop_len():
              raise ValueError("Too many repeated urls, exiting web scraper")     
        else:
          print("Depth exceeded:", depth+1, "out of", max_depth)
          break
      else:
        print("Max URLs reached")
        raise ValueError("Max URLs reached")
    
    return None
  
  def main_crawler(self, url:str, course_name:str, max_urls:int=100, max_depth:int=3, timeout:int=1, stay_on_baseurl:bool=True, depth_or_breadth:str='breadth'):
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
    self.max_urls = max_urls
    self.original_amount = max_urls
    if stay_on_baseurl:
      base_url_str = self.base_url(url)
      print(base_url_str)
    else:
      base_url_str = ''

    # Check for GitHub repository coming soon
    if is_github_repo(url):
      print("Begin Ingesting GitHub page")
      results = self.ingester.ingest_github(url, course_name)
      print("Finished ingesting GitHub page")
      return results
    else:
      try:
        print("Gathering existing urls from Supabase")
        urls = self.supabase_client.table(os.getenv('NEW_NEW_NEWNEW_MATERIALS_SUPABASE_TABLE')).select('course_name, url, contexts').eq('course_name', course_name).execute() # type: ignore

        if urls.data == []:
          self.existing_urls = []
        else:
          self.existing_urls = []
          for row in urls.data:
            whole = ''
            for text in row['contexts']:
              whole += text['text']
            self.existing_urls.append((row['url'], whole, 'supa'))
          print("Finished gathering existing urls from Supabase")
      except Exception as e:
        print("Error:", e)
        print("Could not gather existing urls from Supabase")
        self.existing_urls = []
      try:
        print("Begin Ingesting Web page")
        self.supa_urls = len(self.existing_urls)
        if depth_or_breadth.lower() == 'depth':
          self.depth_crawler(url=url, course_name=course_name, max_depth=max_depth, timeout=timeout, base_url_on=base_url_str)
        elif depth_or_breadth.lower() == 'breadth':
          self.breadth_crawler(url=url, course_name=course_name, timeout=timeout, base_url_on=base_url_str, max_depth=max_depth)
        else:
          raise ValueError("Invalid depth_or_breadth argument")
      except ValueError as e:
        print("Error:", e)


    if len(self.url_contents) < self.original_amount:
      print("Max URLS not reached, returning all urls found:", len(self.url_contents), "out of", self.original_amount)
    elif len(self.url_contents) == self.original_amount:
      print("Max URLS reached:", len(self.url_contents), "out of", self.original_amount)
    else:
      print("Exceeded Max URLS, found:", len(self.url_contents), "out of", self.original_amount)
    print(len(self.url_contents), "urls found")
    print(f"Successfully uploaded files to s3: {len(self.url_contents)}")
    print("Finished /web-scrape")


def is_github_repo(url):
  # Split the URL by '?' to ignore any parameters
  base_url = url.split('?')[0]
  
  # The regular expression now allows for optional 'http', 'https', and 'www' prefixes.
  # It also accounts for optional trailing slashes.
  # The pattern is also case-insensitive.
  pattern = re.compile(r'^(https?://)?(www\.)?github\.com/[^/?]+/[^/?]+/?$', re.IGNORECASE)
  
  # The function returns True or False based on whether the pattern matches the base_url
  return base_url if pattern.match(base_url) else None


def mit_course_download(url:str, course_name:str, local_dir:str):
  '''
  Download an MIT course using its url
  '''
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
  del ingester
  print("Finished Ingest")
  return success_fail

if __name__ == '__main__':
  pass
