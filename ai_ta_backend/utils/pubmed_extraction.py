import os
import requests
import shutil
import xml.etree.ElementTree as ET
import ftplib
import supabase
import gzip
import concurrent.futures
from urllib.parse import urlparse
import tarfile
import os
import shutil
from minio import Minio
import time
from multiprocessing import Manager
import pandas as pd
import threading 
import json
from functools import partial


SUPBASE_CLIENT = supabase.create_client(    # type: ignore
    supabase_url=os.getenv('SUPABASE_URL'), # type: ignore
    supabase_key=os.getenv('SUPABASE_API_KEY')  # type: ignore
)

MINIO_CLIENT = Minio(os.environ['MINIO_URL'],
    access_key=os.environ['MINIO_ACCESS_KEY'],
    secret_key=os.environ['MINIO_SECRET_KEY'],
    secure=True
)

def extractPubmedData():
    """
    Main function to extract metadata and articles from the PubMed baseline folder.
    """
    start_time = time.time()

    ftp_address = "ftp.ncbi.nlm.nih.gov"
    ftp_path = "pubmed/baseline"
    file_list = getFileList(ftp_address, ftp_path, ".gz")
    

    for file in file_list[22:23]:  
        try:
            print("Processing file: ", file)
        
            gz_filepath = downloadXML(ftp_address, ftp_path, file, "pubmed")
            print("GZ Downloaded: ", gz_filepath)
            print("Time taken to download .gz file: ", round(time.time() - start_time, 2), "seconds")
            gz_file_download_time = time.time()

            # extract the XML file
            if not gz_filepath:
                return "failure"
            xml_filepath = extractXMLFile(gz_filepath)
            print("XML Extracted: ", xml_filepath)
            print("Time taken to extract XML file: ", round(time.time() - gz_file_download_time, 2), "seconds")
            
            #xml_filepath = "pubmed/pubmed24n1217.xml"
            for metadata in extractMetadataFromXML(xml_filepath):
                metadata_extract_start_time = time.time() 

                # find PMC ID and DOI for all articles
                metadata_with_ids = getArticleIDs(metadata)
                metadata_update_time = time.time()
                print("Time taken to get PMC ID and DOI for 100 articles: ", round(metadata_update_time - metadata_extract_start_time, 2), "seconds")
                
                # download the articles
                complete_metadata = downloadArticles(metadata_with_ids)
                print(complete_metadata)
                print("Time taken to download articles for 100 articles: ", round(time.time() - metadata_update_time, 2), "seconds")

                # store metadata in csv file
                print("\n")
                print("Total articles retrieved: ", len(complete_metadata))
                df = pd.DataFrame(complete_metadata)
                csv_filepath = "metadata.csv"

                if os.path.isfile(csv_filepath):
                    df.to_csv(csv_filepath, mode='a', header=False, index=False)
                else:
                    df.to_csv(csv_filepath, index=False)
                
                print("Time taken to extract metadata for 100 articles: ", round(time.time() - metadata_extract_start_time, 2), "seconds")


            print("Time taken to download articles: ", round(time.time() - start_time, 2), "seconds")
            print("Total metadata extracted: ", len(complete_metadata))

            # upload articles to bucket
            print("Uploading articles to storage...")
            article_upload = uploadToStorage("pubmed_abstracts")    # need to parallelize upload
            print("Uploaded articles: ", article_upload)
            
            # upload metadata to SQL DB
            df = pd.read_csv(csv_filepath)
            complete_metadata = df.to_dict('records')
            for item in complete_metadata:
                for key, value in item.items():
                    if pd.isna(value):  # Or: math.isnan(value)
                        item[key] = None
            print("Metadata loaded into dataframe: ", len(complete_metadata))
            
            # continue with the rest of the code
            response = SUPBASE_CLIENT.table("publications").upsert(complete_metadata).execute() # type: ignore
            print("Uploaded metadata to SQL DB.")
            
        except Exception as e:
            print("Error processing file: ", e)

        # delete files            
        shutil.rmtree("pubmed_abstracts")
        os.remove("metadata.csv")
        #os.remove(xml_filepath)
        print("Finished file: ", file)
            
    return "success"

def downloadXML(ftp_address: str, ftp_path: str, file: str, local_dir: str):
    """
    Downloads a .gz XML file from the FTP baseline folder and stores it in the local directory.
    Args:
        ftp_address: FTP server address.
        ftp_path: Path to the FTP folder.
        file: File to download.
        local_dir: Local directory to store the downloaded file.
    Returns:
        local_filepath: Path to the downloaded file.
    """
    try:
        # create local directory if it doesn't exist
        os.makedirs(local_dir, exist_ok=True)

        # connect to the FTP server
        ftp = ftplib.FTP(ftp_address)
        ftp.login()
        ftp.cwd(ftp_path) 

        local_filepath = os.path.join(local_dir, file)
        with open(local_filepath, 'wb') as f:
            ftp.retrbinary('RETR ' + file, f.write)
            
        print(f"Downloaded {file} to {local_filepath}")

        ftp.quit()
        return local_filepath
    except Exception as e:
        print("Error downloading file: ", e)
        return None

def getFileList(ftp_address: str, ftp_path: str, extension: str = ".gz"):
    """
    Returns a list of .gz files in the FTP baseline folder.
    Args:
        ftp_address: FTP server address.
        ftp_path: Path to the FTP folder.
        extension: File extension to filter for.
    Returns:
        gz_files: List of .gz files in the FTP folder.
    """
    try:
        # connect to the FTP server
        ftp = ftplib.FTP(ftp_address)
        ftp.login()

        # Change directory to the specified path
        ftp.cwd(ftp_path) 

        # Get list of file entries
        file_listing = ftp.nlst()

        ftp.quit()

        # Filter for files with the specified extension
        gz_files = [entry for entry in file_listing if entry.endswith(extension)]
        gz_files.sort(reverse=True)
        print(f"Found {len(gz_files)} files on {ftp_address}/{ftp_path}")

        return gz_files
    except Exception as e:
        print("Error getting file list: ", e)
        return []

def extractXMLFile(gz_filepath: str):
    """
    Extracts the XML file from the .gz file.
    Args:
        gz_filepath: Path to the .gz file.
    Returns:
        xml_filepath: Path to the extracted XML file.
    """
    try:
        print("Downloaded .gz file path: ", gz_filepath)
        xml_filepath = gz_filepath.replace(".gz", "")
        with gzip.open(gz_filepath, 'rb') as f_in:
            with open(xml_filepath, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        return xml_filepath
    except Exception as e:
        print("Error extracting XML file: ", e)
        return None

def extractMetadataFromXML(xml_filepath: str):
    """
    Extracts article details from the XML file and stores it in a dictionary.
    Details extracted: PMID, PMCID, DOI, ISSN, journal title, article title, 
    last revised date, published date, abstract.
    Args: 
        xml_filepath: Path to the XML file.
    Returns:
        metadata: List of dictionaries containing metadata for each article.
    """
    print("inside extractMetadataFromXML()")
    try:
        # create a directory to store abstracts
        os.makedirs("pubmed_abstracts", exist_ok=True)

        tree = ET.parse(xml_filepath)
        root = tree.getroot()
        metadata = []


        with concurrent.futures.ProcessPoolExecutor() as executor:
            futures = []
            article_items = list(item for item in root.iter('PubmedArticle'))  # Convert generator to list
        
            for item in article_items:
                future = executor.submit(processArticleItem, item)
                article_data = future.result()

                metadata.append(article_data)

                if len(metadata) == 100:
                    print("collected 100 articles")
                    yield metadata
                    metadata = []   # reset metadata for next batch

        if metadata:
            yield metadata
        
        print("Metadata extraction complete.")
    except Exception as e:
        print("Error extracting metadata: ", e)
        return []
    

def processArticleItem(item: ET.Element):
    """
    Extracts article details from a single PubmedArticle XML element. This is used in the process pool executor.
    Args:
        item: PubmedArticle XML element.
    Returns:
        article_data: Dictionary containing metadata for the article.
    """
    try:
        article_data = {}

        medline_citation = item.find('MedlineCitation')
        article = medline_citation.find('Article')
        journal = article.find('Journal')
        issue = journal.find('JournalIssue')

        if medline_citation.find('PMID') is not None:
            article_data['pmid'] = medline_citation.find('PMID').text
            article_data['pmcid'] = None
            article_data['doi'] = None
        else:
            return article_data

        if journal.find('ISSN') is not None:
            article_data['issn'] = journal.find('ISSN').text
        else:
            article_data['issn'] = None

        if journal.find('Title') is not None:
            article_data['journal_title'] = journal.find('Title').text
        else:
            article_data['journal_title'] = None

        # some articles don't have an article title
        article_title = article.find('ArticleTitle')
        if article_title is not None and article_title.text is not None:
            article_data['article_title'] = article_title.text.replace('[', '').replace(']', '')
        else:
            article_data['article_title'] = None

        article_data['last_revised'] = f"{medline_citation.find('DateRevised/Year').text}-{medline_citation.find('DateRevised/Month').text}-{medline_citation.find('DateRevised/Day').text}"
            
        # some articles don't have all fields present for publication date
        if issue.find('PubDate/Year') is not None and issue.find('PubDate/Month') is not None and issue.find('PubDate/Day') is not None:   
            article_data['published'] = f"{issue.find('PubDate/Year').text}-{issue.find('PubDate/Month').text}-{issue.find('PubDate/Day').text}"
        elif issue.find('PubDate/Year') is not None and issue.find('PubDate/Month') is not None:
            article_data['published'] = f"{issue.find('PubDate/Year').text}-{issue.find('PubDate/Month').text}-01"
        elif issue.find('PubDate/Year') is not None:
            article_data['published'] = f"{issue.find('PubDate/Year').text}-01-01"
        else:
            article_data['published'] = None

        # extract and store abstract in a text file
        abstract = article.find('Abstract')
        abstract_filename = None
        if abstract is not None:
            abstract_text = ""
            for abstract_text_element in abstract.iter('AbstractText'):
                # if labels (objective, methods, etc.) are present, add them to the text (e.g. "OBJECTIVE: ")
                if abstract_text_element.attrib.get('Label') is not None:
                    abstract_text += abstract_text_element.attrib.get('Label') + ": "
                if abstract_text_element.text is not None:
                    abstract_text += abstract_text_element.text + "\n"
        
            # save abstract to a text file
            abstract_filename = f"pubmed_abstracts/{article_data['pmid']}.txt"
            with open(abstract_filename, 'w') as f:
                if article_data['journal_title']:
                    f.write("Journal title: " + article_data['journal_title'] + "\n\n")
                if article_data['article_title']:
                    f.write("Article title: " + article_data['article_title'] + "\n\n")
                f.write("Abstract: " + abstract_text)

        # some articles are listed, but not released yet. Adding fields for such articles to maintain uniformity.
        article_data['live'] = True
        article_data['release_date'] = None
        article_data['license'] = None
        article_data['pubmed_ftp_link'] = None
        article_data['filepath'] = abstract_filename

        return article_data
    except Exception as e:
        return {'error': str(e)}

# def getArticleIDs(metadata: list):
#     """
#     Uses the PubMed ID converter API to get PMCID and DOI for each article.
#     Queries the API in batches of 200 articles at a time.
#     Also updates the metadata with the release date and live status - some articles are yet to be released.
#     Args:
#         metadata: List of dictionaries containing metadata for each article.
#     Returns:
#         metadata: Updated metadata with PMCID, DOI, release date, and live status information.
#     """
#     print("In getArticleIDs()")
    
#     base_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
#     app_details = "?tool=ncsa_uiuc&email=caiincsa@gmail.com&format=json"

#     batch_size = 200    # maximum number of articles API can process in one request
            
#     for i in range(0, len(metadata), batch_size):
#         batch = metadata[i:i+batch_size]
#         ids = ",".join([article['pmid'] for article in batch])
#         response = requests.get(base_url + app_details + "&ids=" + ids)
#         data = response.json()        
#         records = data['records']
#         # PARALLELIZE THIS FOR LOOP - UPDATES ADDITIONAL FIELDS FOR ALL ARTICLES AT ONCE
#         with Manager() as manager:
#             shared_metadata = manager.list(batch)
#             with concurrent.futures.ProcessPoolExecutor() as executor:
#                 futures = {executor.submit(updateArticleMetadata, shared_metadata, record): record for record in records}
#                 concurrent.futures.wait(futures)
#             for future in concurrent.futures.as_completed(futures):
#                 record = futures[future]
#                 try:
#                     future.result()
#                 except Exception as exc:
#                     print('%r generated an exception: %s' % (record, exc))
            
#             print("Updated metadata: ", list(shared_metadata))
       
#     print("Length of metadata after ID conversion: ", len(metadata))
                
#     return metadata
    

# def updateArticleMetadata(shared_metadata, record):
#     """
#     Updates metadata with PMCID, DOI, release date, and live status information for given article.
#     Used withing getArticleIDs() function.
#     """
    
#     if 'errmsg' in record:
#         print("Error: ", record['errmsg'])
#         for article in shared_metadata:
#             if article['pmid'] == record['pmid']:
#                 article['live'] = False
#                 break
#     else:
#         # find article with matching pmid and update pmcid, doi, live, and release date fields
#         print("record: ", record)
#         for article in shared_metadata:
#             if article['pmid'] == record['pmid']:
#                 article['pmcid'] = record['pmcid']
#                 article['doi'] = record['doi']
#                 article['live'] = False if 'live' in record and record['live'] == "false" else True
#                 article['release_date'] = record.get('release-date', article['release_date'])
#                 print("Updated metadata in ID converter: ", article)
#                 break

def getArticleIDs(metadata: list):
  """
  Uses the PubMed ID converter API to get PMCID and DOI for each article.
  Queries the API in batches of 200 articles at a time.
  Also updates the metadata with the release date and live status - some articles are yet to be released.
  Args:
      metadata: List of dictionaries containing metadata for each article.
  Returns:
      metadata: Updated metadata with PMCID, DOI, release date, and live status information.
  """
  print("In getArticleIDs()")

  base_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
  app_details = "?tool=ncsa_uiuc&email=caiincsa@gmail.com&format=json"

  batch_size = 200  # maximum number of articles API can process in one request

  for i in range(0, len(metadata), batch_size):
    batch = metadata[i:i + batch_size]
    ids = ",".join([article['pmid'] for article in batch])
    try:
        response = requests.get(base_url + app_details + "&ids=" + ids)
        data = response.json()
        records = data['records']

        # PARALLELIZE THIS FOR LOOP - UPDATES ADDITIONAL FIELDS FOR ALL ARTICLES AT ONCE
        with Manager() as manager:
            shared_metadata = manager.dict()  # Use a shared dictionary
            with concurrent.futures.ProcessPoolExecutor() as executor:
                futures = {
                executor.submit(updateArticleMetadata, shared_metadata, record): record
                for record in records
                }
                concurrent.futures.wait(futures)
                for future in concurrent.futures.as_completed(futures):
                    record = futures[future]
                    try:
                        future.result()
                    except Exception as exc:
                        print('%r generated an exception: %s' % (record, exc))        

            # Update original metadata after loop
            for article in metadata:
                if article['pmid'] in shared_metadata:
                    # print("Shared metadata: ", shared_metadata[article['pmid']])
                    if 'errmsg' in shared_metadata[article['pmid']]:
                        article['live'] = False
                    else:
                        article['pmcid'] = shared_metadata[article['pmid']]['pmcid']
                        article['doi'] = shared_metadata[article['pmid']]['doi']
                        article['live'] = shared_metadata[article['pmid']]['live']
                        article['release_date'] = shared_metadata[article['pmid']]['release_date']
                    #print("Updated metadata: ", article)
    except Exception as e:
        print("Error: ", e)
  #print("Length of metadata after ID conversion: ", len(metadata))
  return metadata


def updateArticleMetadata(shared_metadata, record):
  """
  Updates metadata with PMCID, DOI, release date, and live status information for given article.
  Used within getArticleIDs() function.
  """

  if 'errmsg' in record:
    print("Error: ", record['errmsg'])
    shared_metadata[record['pmid']] = {
        **record,  # Create a copy with record data
        'live': False
    }
  else:
    # Update shared dictionary with pmid as key and updated article data as value
    shared_metadata[record['pmid']] = {
        **record,  # Create a copy with record data
        'pmcid': record['pmcid'],
        'doi': record['doi'],
        'live': False if 'live' in record and record['live'] == "false" else True,
        'release_date': record['release-date'] if 'release-date' in record else None,
    }
    #print("Updated metadata in ID converter: ", shared_metadata[record['pmid']])



# def downloadArticles(metadata: list):
#     """
#     Downloads articles from PMC and stores them in local directory.
#     Args:
#         metadata: List of dictionaries containing metadata for each article.
#     Returns:
#         metadata: Updated metadata with license, FTP link, and downloaded filepath information.
#     """
#     print("In downloadArticles()")
#     try:
#         base_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?"
#         print("Downloading articles...")

#         # connect to FTP server anonymously
#         ftp = ftplib.FTP("ftp.ncbi.nlm.nih.gov")
#         ftp.login()
        
#         for article in metadata:
#             if article['live'] is False or article['pmcid'] is None:
#                 continue

#             # else proceed with download
#             if article['pmcid']:
#                 # query URL for article download
#                 final_url = base_url + "id=" + article['pmcid'] 
#                 print("Download URL: ", final_url)

#                 xml_response = requests.get(final_url)
#                 # get license and FTP link
#                 extracted_data = extractArticleData(xml_response.text) 
#                 print("\nExtracted license and link data: ", extracted_data)

#                 # if no data extracted (reason: article not released/open-access), skip to next article
#                 if not extracted_data:
#                     article['live'] = False
#                     continue
                
#                 # update metadata with license and ftp link information
#                 article['license'] = extracted_data[0]['license']
#                 article['pubmed_ftp_link'] = extracted_data[0]['href'] if 'href' in extracted_data[0] else None
                        
#                 # download the article
#                 ftp_url = urlparse(extracted_data[0]['href'])
#                 ftp_path = ftp_url.path[1:]
#                 print("FTP path: ", ftp_path)

#                 # Set a timeout of 15 minutes - some files take > 1 hour to download and everything hangs
#                 # timeout = threading.Timer(15 * 60, lambda: print("Download timeout reached."))
#                 # timeout.start()
                        
#                 filename = ftp_path.split("/")[-1]
#                 local_file = os.path.join("pubmed_abstracts", filename)

#                 try:
#                     with concurrent.futures.ThreadPoolExecutor() as executor:
#                         future = executor.submit(ftp.retrbinary, 'RETR ' + ftp_path, open(local_file, 'wb').write)
#                         future.result(timeout=15*60)  # Set a timeout of 15 minutes
#                         print("Downloaded PDF file: ", local_file)
#                         article['filepath'] = local_file

#                         # if file is .tar.gz, extract the PDF and delete the tar.gz file
#                         if filename.endswith(".tar.gz"):
#                             extracted_pdf_paths = extractPDF(local_file)
#                             print("Extracted PDFs from .tar.gz file: ", extracted_pdf_paths)
#                             article['filepath'] = ",".join(extracted_pdf_paths)
#                             os.remove(local_file)
#                 except concurrent.futures.TimeoutError:
#                     print("Download timeout reached.")
#                     continue  # Skip the download and continue with the rest of the code
                        
#                 print("\nUpdated metadata after download: ", article) 
        
#         ftp.quit()
#         return metadata   
#     except Exception as e:
#         print("Error downloading articles: ", e)
#         return metadata   

def downloadArticles(metadata: list):
    """
    Downloads articles from PMC and stores them in local directory.
    Args:
        metadata: List of dictionaries containing metadata for each article.
    Returns:
      metadata: Updated metadata with license, FTP link, and downloaded filepath information.
    """
    print("In downloadArticles()")
    try:
        base_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?"

        updated_articles = {}
        
        # Use ThreadPoolExecutor to run download_article for each article in parallel
        download_article_partial = partial(download_article, api_url=base_url)
        with concurrent.futures.ProcessPoolExecutor() as executor:
            futures = [executor.submit(download_article_partial, article) for article in metadata]
            for future in concurrent.futures.as_completed(futures):
                try:
                    print("Starting new download...")
                    updated_article = future.result(timeout=15*60)  # Check result without blocking
                    if updated_article:
                        updated_articles[updated_article['pmid']] = updated_article
                    print("Updated article: ", updated_article)
                except Exception as e:
                    print("Error downloading article:", e)

        # Update original metadata with updated articles
        for article in metadata:
            if article['pmid'] in updated_articles:
                article.update(updated_articles[article['pmid']])
                
        print("Updated metadata after download: ", metadata)
        
        return metadata

    except Exception as e:
        print("Error downloading articles: ", e)
        return metadata

def download_article(article, api_url):
    """
    Downloads the article from given FTP link and updates metadata with license, FTP link, and downloaded filepath information.
    This function is used within downloadArticles() function.
    Args:
        article: Dictionary containing metadata for the article.
        api_url: URL for the article download API.
        ftp: FTP connection object.
    Returns:
        article: Updated metadata for the article.
    """

    print("Downloading articles...")
    if not article['live'] or article['pmcid'] is None:
        return

    # Proceed with download
    # Connect to FTP server anonymously
    ftp = ftplib.FTP("ftp.ncbi.nlm.nih.gov", timeout=15*60)
    ftp.login()

    if article['pmcid']:
        final_url = api_url + "id=" + article['pmcid']
        print("\nDownload URL: ", final_url)

        xml_response = requests.get(final_url)
        extracted_data = extractArticleData(xml_response.text)
        print("Extracted license and link data: ", extracted_data)

        if not extracted_data:
            article['live'] = False
            return

        article['license'] = extracted_data[0]['license']
        article['pubmed_ftp_link'] = extracted_data[0]['href'] if 'href' in extracted_data[0] else None

        ftp_url = urlparse(extracted_data[0]['href'])
        ftp_path = ftp_url.path[1:]
        print("FTP path: ", ftp_path)

        filename = ftp_path.split("/")[-1]
        local_file = os.path.join("pubmed_abstracts", filename)
        
        try:
            with open(local_file, 'wb') as f:
                ftp.retrbinary('RETR ' + ftp_path, f.write)  # Download directly to file

            print("Downloaded FTP file: ", local_file)
            article['filepath'] = local_file

            if filename.endswith(".tar.gz"):
                extracted_pdf_paths = extractPDF(local_file)
                print("Extracted PDFs from .tar.gz file: ", extracted_pdf_paths)
                article['filepath'] = ",".join(extracted_pdf_paths)
                os.remove(local_file)

        except concurrent.futures.TimeoutError:
            print("Download timeout reached.")

        ftp.quit()

        print("\nUpdated metadata after download: ", article)
        return article
         

def extractPDF(tar_gz_filepath: str):
    """
    Extracts PDF files from the downloaded .tar.gz file. The zipped folder contains other supplementary
    materials like images, etc. which are not extracted.
    Args:
        tar_gz_filepath: Path to the .tar.gz file.
    Returns:
        extracted_paths: List of paths to the extracted PDF files.
    """
    try:
        print("Extracting PDF from: ", tar_gz_filepath)
        extracted_paths = []
        with tarfile.open(tar_gz_filepath, "r:gz") as tar:
            for member in tar:
                if member.isreg() and member.name.endswith(".pdf"):
                    tar.extract(member, path="pubmed_abstracts")
                    print("Extracted: ", member.name)
                    extracted_paths.append(os.path.join("pubmed_abstracts", member.name))
                
        return extracted_paths
    except Exception as e:
        print("Error extracting PDF: ", e)
        return []
    
def extractArticleData(xml_string: str):
    """
    Extracts license information and article download link from the XML response.
    This function process XML response for single article.
    Args:
        xml_string: XML response from PMC download API.
    Returns:
        extracted_data: List of dictionaries containing license and download link for the article.
    """
    print("In extractArticleData")
    try:
        root = ET.fromstring(xml_string)
        # if there is an errors (article not open-access), return empty list (skip article)
        if root.find(".//error") is not None:
            return []

        records = root.findall(".//record")
        extracted_data = []
        href = None
        
        for record in records:
            record_id = record.get("id")    # pmcid
            license = record.get("license")
            links = record.findall(".//link")

            for link in links:
                if link.get("format") == "pdf":
                    href = link.get("href")
                    break
            # if PDF link not found, use the available tgz link
            if not href:
                href = links[0].get("href")
            
            extracted_data.append({
                "record_id": record_id,
                "license": license,
                "href": href
            })
        
        return extracted_data
    except Exception as e:
        print("Error extracting article data: ", e)
        return []

def upload_file(client, bucket_name, file_path, object_name):
    """
    Uploads a single file to the Minio bucket.
    """
    try:
        client.fput_object(bucket_name, object_name, file_path)
        print(f"Uploaded: {object_name}")
    except Exception as e:
        print(f"Error uploading {object_name}: {e}")

def uploadToStorage(filepath: str):
    """
    Uploads all files present under given filepath to Minio bucket in parallel.
    """
    print("in uploadToStorage()")
    try:
        bucket_name = "pubmed"

        found = MINIO_CLIENT.bucket_exists(bucket_name)
        if not found:
            MINIO_CLIENT.make_bucket(bucket_name)
            print("Created bucket", bucket_name)
        else:
            print("Bucket", bucket_name, "already exists")

        # Get all files to upload
        files = []
        for root, _, files_ in os.walk(filepath):
            for file in files_:
                file_path = os.path.join(root, file)
                object_name = file_path.split("/")[-1]
                files.append((MINIO_CLIENT, bucket_name, file_path, object_name))

        # Use concurrent.futures ThreadPoolExecutor with limited pool size
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Submit files in batches of 10
            for i in range(0, len(files), 10):
                batch_files = files[i:i+10]
                futures = [executor.submit(upload_file, *args) for args in batch_files]
                for future in futures:
                    future.result()  # This will raise any exceptions from upload_file

        return "success"
    except Exception as e:
        print("Error uploading to storage: ", e)
        return "failure"
  
# def uploadToStorage(filepath: str):
#     """
#     Uploads all files present under given filepath to Minio bucket.
#     """
#     print("in uploadToStorage()")
#     try:
#         bucket_name = "pubmed"
        
#         found = MINIO_CLIENT.bucket_exists(bucket_name)
#         if not found:
#             MINIO_CLIENT.make_bucket(bucket_name)
#             print("Created bucket", bucket_name)
#         else:
#             print("Bucket", bucket_name, "already exists")

#         for root, dirs, files in os.walk(filepath):
#             # can parallelize this upload
#             for file in files:
#                 file_path = os.path.join(root, file)
#                 object_name = file_path.split("/")[-1]
#                 # insert local file into remote bucket
#                 MINIO_CLIENT.fput_object(bucket_name, object_name, file_path)
#                 print("Uploaded: ", object_name)
#         return "success"
#     except Exception as e:
#         print("Error uploading to storage: ", e)
#         return "failure"



        
                        



    
            




    

