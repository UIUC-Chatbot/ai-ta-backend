import os
import requests
import json
import arxiv
import crossref_commons.retrieval
import xml.etree.ElementTree as ET
import ftplib
from urllib.parse import urlparse


# Below functions hit API endpoints from sites like arXiv, Elsevier, and Sringer Nature to retrieve journal articles
SPRINGER_API_KEY = os.environ.get('SPRINGER_API_KEY')
ELSEVIER_API_KEY = os.environ.get('ELSEVIER_API_KEY')

def getFromDoi(doi: str):
    """
    This function takes DOI string as input and downloads the 
    article from the publisher's website.
    Args:
        doi: DOI string
    Returns:
        success: string
        failed: string (if the article is not accessible)
    """
    # get metadata from crossref
    metadata = get_article_metadata_from_crossref(doi)
    print("Publisher: ", metadata['publisher'])
    print("Content domain: ", metadata['content-domain'])
    publisher = metadata['publisher'].lower().split()
    
    if 'springer' in publisher:
        # download from springer
        downloadSpringerFulltext(doi=doi)
    elif 'elsevier' in publisher:
        # download from elsevier
        downloadElsevierFulltextFromDoi(doi=doi)
    else:
        print("Publisher not supported yet. Please try again later.")
    return "success"

def get_arxiv_fulltext(query: str):
    """
    This function retrieves journal articles from arXiv
    """
    search = arxiv.Search(query=query, 
                          max_results=10, 
                          sort_by = arxiv.SortCriterion.SubmittedDate)

    directory = os.path.join(os.getcwd(), 'arxiv_papers')
    if not os.path.exists(directory):
        os.makedirs(directory)

    for result in arxiv.Client().results(search):
        print("Downloading paper: ", result.title)
        result.download_pdf(dirpath=directory)

    return "success"

def get_article_link_from_doi(doi: str) -> str:
    """
    This function calls the doi.org API to retrieve the link to the journal article
    """    
    prefix = "https://doi.org/api/handles/"

    url = prefix + doi
    response = requests.get(url)
    data = response.json()
    article_link = data['values'][0]['data']['value']

    return article_link

def get_article_metadata_from_crossref(doi: str):
    """
    This function calls the crossref.org API to retrieve the metadata of the journal article
    """    
    metadata = crossref_commons.retrieval.get_publication_as_json(doi)
    return metadata

def downloadSpringerFulltext(issn=None, subject=None, journal=None, title=None, doi=None):
    """
    This function uses the Springer Nature API to download openaccess journal articles.
    Args:
        issn: limit to ISSN number of the journal/book
        subject: limit articles to a specific subject - Chemistry, Physics, etc.
        journal: limit to keywords occuring in journal title
        title: limit to keywords occuring in article title
    The initial API response returns a list of articles with metadata.
    
    """
    directory = os.path.join(os.getcwd(), 'springer_papers')
    if not os.path.exists(directory):
        os.makedirs(directory)
    api_url = "http://api.springernature.com/openaccess/json?q="
    headers = {'Accept': 'application/json'}

    if doi:
        # query by doi
        query_str = "doi:" + doi
    elif issn:
        # query by issn
        query_str = "issn:" + issn
    elif journal:   
        # query by journal title
        query_str = "journal:" + journal
    elif title:
        # query by article title
        query_str = "title:" + title
    elif subject:
        # query by subject
        query_str = "subject:" + subject
    else:
        return "No query parameters provided"
    
    main_url = api_url + query_str + "&api_key=" + str(SPRINGER_API_KEY)
    print("Full URL: ", main_url)

    response = requests.get(main_url)
    print("Status: ", response.status_code)
    data = response.json()
    print("Total records: ", len(data['records']))
    

    for record in data['records']: 
        urls = record['url']
        filename = record['doi'].replace("/", "_")
        print("Filename: ", filename)

        if len(urls) > 0:
            url = urls[0]['value'] + "?api_key=" + str(SPRINGER_API_KEY)
            print("DX URL: ", url)
            url_response = requests.get(url, headers=headers)
            dx_doi_data = url_response.json()
            links = dx_doi_data['link']
            pdf_link = None
            for link in links:
                if link['content-type'] == 'application/pdf' and link['intended-application'] == 'text-mining':
                    pdf_link = link['URL']
                    print("PDF Link: ", pdf_link)
                    break
            
            if pdf_link:
                response = requests.get(pdf_link)
                with open(directory + "/" + filename + ".pdf", "wb") as f:  # Open a file in binary write mode ("wb")
                    for chunk in response.iter_content(chunk_size=1024):  # Download in chunks
                        f.write(chunk)
                print("Downloaded: ", filename)
                
    return "success"


def downloadElsevierFulltextFromDoi(doi: str):
    """
    This function downloads articles from Elsevier for a given DOI.
    """
    directory = os.path.join(os.getcwd(), 'elsevier_papers')
    if not os.path.exists(directory):
        os.makedirs(directory)

    headers = {'X-ELS-APIKey': ELSEVIER_API_KEY, 'Accept':'application/pdf'}

    url = 'https://api.elsevier.com/content/article/doi/' + doi
    response = requests.get(url, headers=headers)
    print("Status: ", response.status_code)
    data = response.text
    filename = doi.replace("/", "_")
    with open(directory + "/" + filename + ".pdf", "wb") as f:  # Open a file in binary write mode ("wb")
        for chunk in response.iter_content(chunk_size=1024):  # Download in chunks
            f.write(chunk)

    return "success"

def extract_record_data(xml_string):
    """Extracts record ID, license, and href elements from an XML string.
    Args:
        xml_string: XML string --> Response from the OA Web Service API
    Returns:
        extracted_data: list of dictionaries
    """
    root = ET.fromstring(xml_string)
    records = root.findall(".//record")
    extracted_data = []

    for record in records:
        record_id = record.get("id")
        license = record.get("license")
        href = record.find(".//link").get("href")
        extracted_data.append({
            "record_id": record_id,
            "license": license,
            "href": href
        })

    return extracted_data

def downloadPubmedArticles(id=None, from_date=None, until_date=None, format=None):
    """
    This function downloads articles from PubMed using the OA Web Service API.
    """
    directory = os.path.join(os.getcwd(), 'pubmed_papers')
    if not os.path.exists(directory):
        os.makedirs(directory)

    main_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?"
    if id:
        main_url += "id=" + id
    elif from_date and until_date:
        main_url += "from=" + from_date + "&until=" + until_date
    elif from_date:
        main_url += "from=" + from_date
    else:
        return "No query parameters provided"
    
    if format != None and format in ['tgz', 'pdf']:
        main_url += "&format=" + format

    print("Full URL: ", main_url)

    xml_response = requests.get(main_url)
    root = ET.fromstring(xml_response.text)
    resumption = root.find(".//resumption")

    while resumption is not None: # download current articles and query 
        # parse xml response and extract pdf links and other metadata
        records = extract_record_data(xml_response.text)
        print("Total records: ", len(records))
        if len(records) > 0:
            # download articles
            download_status = downloadFromFTP(records, directory, ftp_address="ftp.ncbi.nlm.nih.gov")

        # query for next set of articles    
        resumption_url = resumption.find(".//link").get("href")
        print("Resumption URL: ", resumption_url)

        xml_response = requests.get(resumption_url)
        root = ET.fromstring(xml_response.text)
        resumption = root.find(".//resumption")

    # download current articles if resumption is None
    records = extract_record_data(xml_response.text)
    print("Current total records: ", len(records))
    if len(records) > 0:
        # download articles
        download_status = downloadFromFTP(records, directory, ftp_address="ftp.ncbi.nlm.nih.gov")

    return "success"

    
    

def downloadFromFTP(paths, local_dir, ftp_address):
    """
    This function downloads files from an FTP server.
    Args:
        paths: list of FTP paths
        local_dir: local directory to save the files
        ftp_address: ftp address
    """
    # Connect to the FTP server anonymously
    ftp = ftplib.FTP(ftp_address)
    ftp.login()  # Use anonymous login

    # Download each file in the list
    for path in paths:
        ftp_url = urlparse(path['href'])
        ftp_path = ftp_url.path[1:]
        print("Downloading from FTP path: ", ftp_path)

        filename = ftp_path.split('/')[-1]
        local_file = os.path.join(local_dir, filename)
        with open(local_file, 'wb') as f:
            ftp.retrbinary("RETR " + ftp_path, f.write)

        ftp.quit()
        print("Downloaded: ", filename)
    
    return "success"
