import os
import shutil
import requests
import json
import arxiv
import crossref_commons.retrieval
import xml.etree.ElementTree as ET
import ftplib
from urllib.parse import urlparse

from ai_ta_backend.aws import upload_data_files_to_s3
from ai_ta_backend.vector_database import Ingest


# Below functions hit API endpoints from sites like arXiv, Elsevier, and Sringer Nature to retrieve journal articles
SPRINGER_API_KEY = os.environ.get('SPRINGER_API_KEY')
ELSEVIER_API_KEY = os.environ.get('ELSEVIER_API_KEY')

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
    
    main_url = api_url + query_str + "&api_key=" + str(SPRINGER_API_KEY)
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

        # query for next page
        next_page_url = "http://api.springernature.com" + data['nextPage']
        response = requests.get(next_page_url)
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
    
    # # upload to s3
    # s3_paths = upload_data_files_to_s3(course_name, directory)

    # # Delete files from local directory
    # shutil.rmtree(directory)

    # # ingest into QDRANT
    # ingest = Ingest()
    # journal_ingest = ingest.bulk_ingest(s3_paths, course_name=course_name)
                                
    return "success"


def downloadElsevierFulltextFromDoi(doi: str, course_name: str):
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

    # # upload to s3
    # s3_paths = upload_data_files_to_s3(course_name, directory)

    # # Delete files from local directory
    # shutil.rmtree(directory)

    # # ingest into QDRANT
    # ingest = Ingest()
    # journal_ingest = ingest.bulk_ingest(s3_paths, course_name=course_name)

    return "success"

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

    # # upload to s3
    # s3_paths = upload_data_files_to_s3(course_name, directory)

    # # Delete files from local directory
    # shutil.rmtree(directory)

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
        journal_query = journal.replace(" ", "+") + "[Journal]"
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
    
    total_records = int(data['esearchresult']['count'])
    total_records = 500
    current_records = len(data['esearchresult']['idlist'])
    id_list = data['esearchresult']['idlist']
    
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
    root = ET.fromstring(response.text)
    records = root.findall(".//record")
    for record in records:
        pmcid = record.get("pmcid")
        if pmcid:
            pmcid_list.append(pmcid)
    
    return pmcid_list
    
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
    ftp.quit()
        
    
    return "success"
