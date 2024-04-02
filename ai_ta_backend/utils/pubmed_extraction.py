import os
import requests
import shutil
import json
import xml.etree.ElementTree as ET
import ftplib
import supabase
import gzip
import time
import concurrent.futures
import urllib.request


SUPBASE_CLIENT = supabase.create_client(    # type: ignore
    supabase_url=os.getenv('SUPABASE_URL'), # type: ignore
    supabase_key=os.getenv('SUPABASE_API_KEY')  # type: ignore
)

def extractPubmedData():
    """
    Extracts metadata from the files listed in FTP folder and stores it in SQL DB.
    """
    ftp_address = "ftp.ncbi.nlm.nih.gov"
    ftp_path = "pubmed/baseline"
    file_list = getFileList(ftp_address, ftp_path, ".gz")

    for file in file_list:
        # download the .gz file
        gz_filepath = downloadFromFTP(ftp_address, ftp_path, file, "pubmed")
        print("Downloaded: ", gz_filepath)

        # extract the XML file
        xml_filepath = extractXMLFile(gz_filepath)
        print("XML Extracted: ", xml_filepath)

        # extract metadata from the XML file
        metadata = extractMetadataFromXML(xml_filepath)

        # find PMC ID and DOI for all articles
        for article in metadata:
            pmid = article['pmid']
            article_ids = getArticleIDs(pmid)

        
        # delete XML and .gz files
        

    
    return "success"

def downloadFromFTP(ftp_address: str, ftp_path: str, file: str, local_dir: str):
    """
    Downloads all .gz files from the FTP folder and stores it in the local directory.
    """
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
    
    return "success"

def getFileList(ftp_address: str, ftp_path: str, extension: str = ".gz"):
    """
    Returns a list of files in the FTP folder.
    """
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

def extractXMLFile(gz_filepath: str):
    """
    Extracts the XML file from the .gz file.
    Args:
        gz_filepath: Path to the .gz file.
    Returns:
        xml_filepath: Path to the extracted XML file.
    """
    print("gz file path: ", gz_filepath)
    xml_filepath = gz_filepath.replace(".gz", "")
    with gzip.open(gz_filepath, 'rb') as f_in:
        with open(xml_filepath, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    return xml_filepath

def extractMetadataFromXML(xml_filepath: str):
    """
    Extracts metadata from the XML file and stores it in a dictionary.
    Args: 
        xml_filepath: Path to the XML file.
    Returns:
        metadata: List of dictionaries containing metadata for each article.
    """
    tree = ET.parse(xml_filepath)
    root = tree.getroot()
    metadata = []
    # Extract metadata from the XML file
    for item in root.iter('PubmedArticle'):
        article_data = {}

        publication_status = item.find('PubmedData/PublicationStatus').text
        # ppublish articles are not present in PMC database
        if publication_status == "epublish":
            article_data['full_text'] = True
        else:
            article_data['full_text'] = False

        medline_citation = item.find('MedlineCitation')
        article = medline_citation.find('Article')
        journal = article.find('Journal')
        issue = journal.find('JournalIssue')

        article_data['pmid'] = medline_citation.find('PMID').text
        article_data['issn'] = journal.find('ISSN').text
        article_data['journal_title'] = journal.find('Title').text

        article_title = article.find('ArticleTitle').text
        article_data['article_title'] = article_title.replace('[', '').replace(']', '')

        article_data['last_revised'] = f"{medline_citation.find('DateRevised/Year').text}-{medline_citation.find('DateRevised/Month').text}-{medline_citation.find('DateRevised/Day').text}"
        article_data['published'] = f"{issue.find('PubDate/Year').text}-{issue.find('PubDate/Month').text}-{issue.find('PubDate/Day').text}"
        #article_data['date_completed'] = f"{medline_citation.find('DateCompleted/Year').text}-{medline_citation.find('DateCompleted/Month').text}-{medline_citation.find('DateCompleted/Day').text}"

        # extract and store abstract in a text file
        


        metadata.append(article_data)
        
    return metadata

def getArticleIDs(pmid: str):
    """
    Retrieves the PMC ID and DOI for an article.
    """
    base_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
    app_details = "?tool=ncsa_uiuc&email=caiincsa@gmail.com"
    url = base_url + app_details + "&ids=" + id

    response = requests.get(url)



    

