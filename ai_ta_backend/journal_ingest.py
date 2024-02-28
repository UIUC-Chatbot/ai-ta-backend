import os
import shutil
import requests
import json
import arxiv
import crossref_commons.retrieval
import xml.etree.ElementTree as ET
import ftplib
from urllib.parse import urlparse
import urllib.parse

from ai_ta_backend.aws import upload_data_files_to_s3
from ai_ta_backend.vector_database import Ingest

import supabase
import tarfile

import time

# Below functions hit API endpoints from sites like arXiv, Elsevier, and Sringer Nature to retrieve journal articles
SPRINGER_API_KEY = os.environ.get('SPRINGER_API_KEY')
ELSEVIER_API_KEY = os.environ.get('ELSEVIER_API_KEY')

SUPABASE_CLIENT = supabase.create_client(  # type: ignore
      supabase_url=os.getenv('SUPABASE_URL'),  # type: ignore
      supabase_key=os.getenv('SUPABASE_API_KEY'))  # type: ignore

##------------------------ DOI FUNCTIONS ------------------------##

def getFromDoi(doi: str, course_name: str):
    """
    This function takes DOI string as input and downloads the article from the publisher's website.
    Publishers covered: Springer Nature, Elsevier, PubMed
    Args:
        doi: DOI string
    """
    # get metadata from crossref
    metadata = get_article_metadata_from_crossref(doi)
    print("Publisher: ", metadata['publisher'])
    print("Content domain: ", metadata['content-domain'])
    publisher = metadata['publisher'].lower().split()
    #print("Metadata:", metadata)

    if 'springer' in publisher:
        # download from springer
        downloadSpringerFulltext(doi=doi, course_name=course_name)
    elif 'elsevier' in publisher:
        # download from elsevier
        downloadElsevierFulltextFromDoi(doi=doi, course_name=course_name)
    else:
        print("No direct openaccess link found. Searching PubMed...")

        pmcid = pubmed_id_converter(doi)
        if pmcid:
            print("Article found in PubMed. Downloading...")
            downloadPubmedArticles(id=pmcid, course_name=course_name)
        else:
            print("Article not found in our current databases, please try again later.")

    return "success"

def get_article_link_from_doi(doi: str) -> str:
    """
    This function calls the doi.org API to retrieve the link to the journal article.
    """    
    prefix = "https://doi.org/api/handles/"

    url = prefix + doi
    response = requests.get(url)
    data = response.json()
    article_link = data['values'][0]['data']['value']

    return article_link

def get_article_metadata_from_crossref(doi: str):
    """
    This function calls the crossref.org API to retrieve the metadata of a journal article.
    """    
    metadata = crossref_commons.retrieval.get_publication_as_json(doi)
    return metadata

##------------------------ ARXIV API FUNCTIONS ------------------------##

def get_arxiv_fulltext(query = "", ids = None, course_name = None):
    """
    This function retrieves journal articles from arXiv
    based on search query or article IDs or a combination of both.
    """
    
    if ids:
        search = arxiv.Search(id_list=[ids], 
                          max_results=10, 
                          sort_by = arxiv.SortCriterion.SubmittedDate)
    elif query:
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


##------------------------ SPRINGER NATURE API FUNCTIONS ------------------------##

def downloadSpringerFulltext(issn=None, subject=None, journal=None, title=None, doi=None, course_name=None):
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
        journal = "%22" + journal.replace(" ", "%20") + "%22"
        query_str = "journal:" + journal
    elif title:
        # query by article title
        title = "%22" + title.replace(" ", "%20") + "%22"
        query_str = "title:" + title
        print("Title: ", title)
    elif subject:
        # query by subject
        query_str = "subject:" + subject
    else:
        return "No query parameters provided"
    
    main_url = api_url + query_str + "&api_key=" + str(SPRINGER_API_KEY) + "&s=301"
    print("Full URL: ", main_url)
    

    response = requests.get(main_url)
    print("Status: ", response.status_code)
    data = response.json()
    print("Total records: ", len(data['records']))
    
    while 'nextPage' in data:
        # extract current page data
        for record in data['records']: 
            urls = record['url']
            filename = record['doi'].replace("/", "_")
            print("Filename: ", filename)

            if len(urls) > 0:
                url = urls[0]['value'] + "?api_key=" + str(SPRINGER_API_KEY)
                print("DX URL: ", url)
                url_response = requests.get(url, headers=headers)
                # check for headers here!

                print("Headers: ", url_response.headers['content-type'])
                
                dx_doi_data = url_response.json()
                links = dx_doi_data['link']
                pdf_link = None
                for link in links:
                    if link['content-type'] == 'application/pdf' and link['intended-application'] == 'text-mining':
                        pdf_link = link['URL']
                        print("PDF Link: ", pdf_link)
                        break
                
                if pdf_link:
                    try:
                        response = requests.get(pdf_link)
                        with open(directory + "/" + filename + ".pdf", "wb") as f:  # Open a file in binary write mode ("wb")
                            for chunk in response.iter_content(chunk_size=1024):  # Download in chunks
                                f.write(chunk)
                        print("Downloaded: ", filename)
                    except Exception as e:
                        print("Error: ", e)

        # query for next page
        next_page_url = "http://api.springernature.com" + data['nextPage']
        response = requests.get(next_page_url)
        print("Next page URL: ", next_page_url)
        data = response.json()
        # print("Total records: ", len(data['records']))

    # last set of records after exiting while loop
    for record in data['records']: 
        urls = record['url']
        filename = record['doi'].replace("/", "_")
        # print("Filename: ", filename)

        if len(urls) > 0:
            url = urls[0]['value'] + "?api_key=" + str(SPRINGER_API_KEY)
            # print("DX URL: ", url)
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
                try:
                    response = requests.get(pdf_link)
                    with open(directory + "/" + filename + ".pdf", "wb") as f:  # Open a file in binary write mode ("wb")
                        for chunk in response.iter_content(chunk_size=1024):  # Download in chunks
                            f.write(chunk)
                    print("Downloaded: ", filename)
                except Exception as e:
                    print("Error: ", e)
    
    # upload to supabase bucket
    try:
        for root, directories, files in os.walk(directory):
            for file in files:
                filepath = os.path.join(root, file)
                print("Uploading: ", file)
                uppload_path = "springer_papers/" + file
                try:
                    with open(filepath, "rb") as f:
                        res = SUPABASE_CLIENT.storage.from_("publications/springer_journals/nature_immunology").upload(file=f, path=uppload_path, file_options={"content-type": "application/pdf"})
                        print("Upload response: ", res)
                except Exception as e:
                    print("Error: ", e)
            
    except Exception as e:
        print("Error: ", e)
                
    # # upload to s3
    # s3_paths = upload_data_files_to_s3(course_name, directory)

    # # Delete files from local directory
    # shutil.rmtree(directory)

    # # ingest into QDRANT
    # ingest = Ingest()
    # journal_ingest = ingest.bulk_ingest(s3_paths, course_name=course_name)
                                
    return "success"

##------------------------ ELSEVIER API FUNCTIONS ------------------------##

def downloadElsevierFulltextFromDoi(id: str, id_type: str, course_name: str):
    """
    This function downloads articles from Elsevier for a given DOI.
    Modify the function to accept all sorts of IDs - pii, pubmed_id, eid
    """
    

    directory = os.path.join(os.getcwd(), 'elsevier_papers')
    if not os.path.exists(directory):
        os.makedirs(directory)

    headers = {'X-ELS-APIKey': ELSEVIER_API_KEY, 'Accept':'application/pdf'}
    url = 'https://api.elsevier.com/content/article/'

    if id_type == "doi":
        url += "doi/" + id
    elif id_type == "eid":
        url += "eid/" + id
    elif id_type == "pii":
        url += "pii/" + id
    elif id_type == "pubmed_id":
        url += "pubmed_id/" + id
    else:
        return "No query parameters provided"

    response = requests.get(url, headers=headers)
    print("Status: ", response.status_code)
    data = response.text
    filename = id.replace("/", "_")
    with open(directory + "/" + filename + ".pdf", "wb") as f:  # Open a file in binary write mode ("wb")
        for chunk in response.iter_content(chunk_size=1024):  # Download in chunks
            f.write(chunk)
    print("Downloaded: ", filename)
    # # upload to s3
    # s3_paths = upload_data_files_to_s3(course_name, directory)

    # # Delete files from local directory
    # shutil.rmtree(directory)

    # # ingest into QDRANT
    # ingest = Ingest()
    # journal_ingest = ingest.bulk_ingest(s3_paths, course_name=course_name)

    return "success"

def searchScienceDirectArticles(course: str, query: str, title: str, pub: str):
    """
    This function is used for a text-based search in ScienceDirect.
    Args:
        course: course name
        query: search query
        title: article title
        journal: journal title
    """
    
    data = {
        "filter": {
            "openAccess": True
        },
        "display": {
            "offset": 0,
            "show": 50
        }
    }

    # read parameters from request
    if query:
        data["qs"] = query
    if title:
        data["title"] = title
    if pub:
        data["pub"] = pub

    url = "https://api.elsevier.com/content/search/sciencedirect?"
    headers = {'X-ELS-APIKey': ELSEVIER_API_KEY, 'Accept':'application/json'}

    response = requests.put(url, headers=headers, json=data)
    print("Status: ", response.status_code)
    response_data = response.json()
    results = response_data['results']
    total_results = response_data['resultsFound']
    print("Total results: ", total_results)
    current_results = len(results)  

    # iterate through results and extract doi and pii
    for result in results:
        doi = result['doi']
        #pii = result['pii']
        if doi:
            downloadElsevierFulltextFromDoi(id=doi, id_type='doi', course_name=course)
        # elif pii:
        #     # download with pii
        #     pass

    # paginate through results if total > current 
    while current_results < total_results:
        
        data["display"]["offset"] += current_results
        response = requests.put(url, headers=headers, json=data)
        print("Status: ", response.status_code)
        response_data = response.json()
        results = response_data['results']
        current_results += len(results)
        print("Current results: ", current_results)

        # iterate through results and extract doi and pii
        for result in results:
            doi = result['doi']
            #pii = result['pii']
            if doi:
                downloadElsevierFulltextFromDoi(id=doi, id_type='doi', course_name=course)
            # elif pii:
            #     # download with pii
            #     pass

    return "success"

def searchScopusArticles(course: str, query: str, title: str, pub: str, subject: str, issn: str):
    """
    This function uses the Scopus Search API to retrieve metadata for journal articles
    and then downloads the fulltext using downloadElsevierFulltextFromDoi().
    """
    # log start time
    start_time = time.monotonic()

    directory = os.path.join(os.getcwd(), 'elsevier_papers')
    if not os.path.exists(directory):
        os.makedirs(directory)

    # uses GET request
    base_url = "https://api.elsevier.com/content/search/scopus?"
    query = "query="
    # read parameters from request
    if issn:
        query += "ISSN(" + issn + ")"

    if pub:
        query += "SRCTITLE(" + pub + ")"
    if title:
        query += "TITLE(" + title + ")"
    if subject:
        query += "SUBJAREA(" + subject + ")"

    final_url = base_url + query + "OPENACCESS(1)" + "&apiKey=" + str(ELSEVIER_API_KEY)
    print("Final URL: ", final_url)

    encoded_url = urllib.parse.quote(final_url, safe=':/?&=')
    response = requests.get(encoded_url)
    print("Status: ", response.status_code)
    data = response.json()

    # iterate through results and extract full-text links
    results = data['search-results']['entry']
    for result in results:
        # results contain pii - so we can call downloadElsevierFulltextFromDoi() here 
        print("PII: ", result['pii'])
        pii = result['pii']
        download_status = downloadElsevierFulltextFromDoi(id=pii, id_type='pii', course_name=course)
        print("Download status: ", download_status)


    # response is JSON and has next page link
    links = data['search-results']['link']
    next_page_url = None
    for link in links:
        if link['@ref'] == 'next':
            next_page_url = link['@href']
            break
    print("Next page: ", next_page_url)
    while next_page_url:
        response = requests.get(next_page_url)
        data = response.json()
        results = data['search-results']['entry']
        for result in results:
            # results contain pii - so we can call downloadElsevierFulltextFromDoi() here 
            pii = result['pii']
            download_status = downloadElsevierFulltextFromDoi(id=pii, id_type='pii', course_name=course)
            print("Download status: ", download_status)

        # response is JSON and has next page link
        links = data['search-results']['link']
        for link in links:
            if link['@ref'] == 'next':
                next_page_url = link['@href']
                break
        print("Next page: ", next_page_url)

    # upload to supabase bucket
    try:
        for root, directories, files in os.walk(directory):
            for file in files:
                filepath = os.path.join(root, file)
                print("Uploading: ", file)
                uppload_path = "springer_papers/" + file
                try:
                    with open(filepath, "rb") as f:
                        res = SUPABASE_CLIENT.storage.from_("publications/elsevier_journals/cell_host_and_mircobe").upload(file=f, path=uppload_path, file_options={"content-type": "application/pdf"})
                        print("Upload response: ", res)
                except Exception as e:
                    print("Error: ", e)
            
    except Exception as e:
        print("Error: ", e)

    # log end time
    print(f"⏰ Runtime: {(time.monotonic() - start_time):.2f} seconds")

    return "success"



##------------------------ PUBMED API FUNCTIONS ------------------------##

def downloadPubmedArticles(id, course_name, **kwargs):
    """
    This function downloads articles from PubMed using the OA Web Service API.
    Search is based on PubMed ID, date range, and file format.
    Args:
        id: PubMed ID
        from_date: start date
        until_date: end date
        format: file format - pdf or tgz
    """
    from_date = kwargs.get('from_date', None)
    until_date = kwargs.get('until_date', None)
    format = kwargs.get('format', None)

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

    # upload to supabase bucket
    # try:
    #     for root, directories, files in os.walk(directory):
    #         for file in files:
    #             filepath = os.path.join(root, file)
    #             print("Uploading: ", file)
    #             uppload_path = "pubmed_articles/" + file
    #             with open(filepath, "rb") as f:
    #                 res = SUPABASE_CLIENT.storage.from_("publications").upload(file=f, path=uppload_path, file_options={"content-type": "application/pdf"})
    #                 print("Upload response: ", res)
            
    # except Exception as e:
    #     print("Error: ", e)
    # # upload to s3
    # s3_paths = upload_data_files_to_s3(course_name, directory)

    # # Delete files from local directory
    #shutil.rmtree(directory)

    # # ingest into QDRANT
    # ingest = Ingest()
    # journal_ingest = ingest.bulk_ingest(s3_paths, course_name=course_name)

    return "success"

def searchPubmedArticlesWithEutils(course: str, search: str, title: str, journal: str):
    """
    This function is used for a text-based search in PubMed using the E-Utilities API.
    Args:
        course: course name
        query: search query
        title: article title
        journal: journal title
    """
    directory = os.path.join(os.getcwd(), 'pubmed_papers')
    if not os.path.exists(directory):
        os.makedirs(directory)

    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
    database = "db=pmc"
    final_query = "term="
    
    title_query = journal_query = search_query = ""
    if title:
        title_query = title.replace(" ", "+") + "[Title]"
        final_query += title_query + "+AND+"
    else:
        final_query += title_query
    if journal:
        journal_query = journal.replace(" ", "+") + "[ta]"
        final_query += journal_query + "+AND+"
    else:
        final_query += journal_query
    if search:
        search_query = search.replace(" ", "+")
        final_query += search_query
    
    final_url = base_url + database + "&" + final_query + "&retmode=json&retmax=100"
    print("Final URL: ", final_url)
    response = requests.get(final_url)
    data = response.json()

    print(data)
    
    total_records = int(data['esearchresult']['count'])
    current_records = len(data['esearchresult']['idlist'])
    id_list = data['esearchresult']['idlist']

    print("Total Records: ", total_records)
    print("Current Records: ", current_records)
    print("ID List: ", id_list)

    while current_records < total_records:
        retstart = current_records
        final_url = base_url + database + "&" + final_query + "&retmode=json&retmax=100&retstart=" + str(retstart)
        print("Final URL: ", final_url)
        response = requests.get(final_url)
        data = response.json()

        current_ids = data['esearchresult']['idlist']
        id_list += current_ids
        current_records += len(current_ids)
        print("Current Records: ", current_records)

        id_str = ",".join(id_list)
        current_pmc_ids = pubmed_id_converter(id_str)
        
        # call pubmed download here 
        for pmc_id in current_pmc_ids:
            downloadPubmedArticles(id=pmc_id, course_name=course)
    
    id_str = ",".join(id_list)
    current_pmc_ids = pubmed_id_converter(id_str)
    print("Current PMC IDs: ", current_pmc_ids)
        
    # call pubmed download here 
    for pmc_id in current_pmc_ids:
        downloadPubmedArticles(id=pmc_id, course_name=course)

    return "success"


def pubmed_id_converter(id: str):
    """
    This function is used to convert DOI to PubMed ID.
    Can also be used to convert PubMed ID to DOI.
    """
    pmcid_list = []
    base_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
    app_details = "?tool=ncsa_uiuc&email=caiincsa@gmail.com"
    url = base_url + app_details + "&ids=" + id
    
    response = requests.get(url)
    print("Response: ", response.text)
    root = ET.fromstring(response.text)
    records = root.findall(".//record")
    for record in records:
        pmcid = record.get("pmcid")
        if pmcid:
            pmcid_list.append(pmcid)
    
    return pmcid_list


def extract_record_data(xml_string):
    """
    It is used to parse the response from the OA Web Service API - downloadPubmedArticles().
    Extracts record ID, license, and href elements from an XML string.
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
    

def downloadFromFTP(paths, local_dir, ftp_address):
    """
    This function downloads files from an FTP server. 
    Used in conjunction with downloadPubmedArticles().
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
        print("Downloaded: ", filename)

        # if filename ends in tar.gz, extract the pdf and delete the tar.gz
        if filename.endswith(".tar.gz"):
            extracted_pdf = extract_pdf(local_file)
            os.remove(local_file)
    ftp.quit()
        
    
    return "success"


def extract_pdf(tar_gz_file):
  """
  Extracts a PDF file from a tar.gz archive and stores it in the same folder.

  Args:
    tar_gz_file: The path to the tar.gz file.
  """

  with tarfile.open(tar_gz_file, "r:gz") as tar:
    for member in tar:
      # Check if it's a regular file and ends with .pdf extension
      if member.isreg() and member.name.endswith(".pdf"):
        # get the file name
        
        # Extract the file to the same directory
        tar.extract(member, path="pubmed_papers")

        return member.name