import os
import json
import time
import pandas as pd
import shutil
import requests
import supabase
import concurrent.futures
from crossref.restful import Works, Journals
from ai_ta_backend.database import aws, sql

SPRINGER_API_KEY = os.environ.get('SPRINGER_API_KEY')
LICENSES = {
    "http://onlinelibrary.wiley.com/termsAndConditions#vor": "closed_access",
    "http://creativecommons.org/licenses/by/4.0/": "CC BY",
    "http://creativecommons.org/licenses/by-nc/4.0/": "CC BY-NC",
    "http://creativecommons.org/licenses/by-nc-nd/4.0/": "CC BY-NC-ND",
    "http://creativecommons.org/licenses/by-nc-sa/4.0/": "CC BY-NC-SA",
}

s3_client = aws.AWSStorage()
aws_bucket = os.getenv('S3_BUCKET_NAME')
supabase_client = supabase.create_client(  # type: ignore
      supabase_url=os.environ['SUPABASE_URL'], supabase_key=os.environ['SUPABASE_API_KEY'])


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
    print("in downloadSpringerFulltext")
    # create directory to store files
    directory = os.path.join(os.getcwd(), 'springer_papers')
    if not os.path.exists(directory):
        os.makedirs(directory)

    # set headers
    api_url = "http://api.springernature.com/openaccess/json?q="
    headers = {'Accept': 'application/json'}

    # form the query URL based on the input parameters received
    if doi:
        query_str = "doi:" + doi
    elif issn:
        query_str = "issn:" + issn
    elif journal:   
        journal = "%22" + journal.replace(" ", "%20") + "%22"
        query_str = "journal:" + journal
    elif title:
        title = "%22" + title.replace(" ", "%20") + "%22"
        query_str = "title:" + title
    elif subject:
        query_str = "subject:" + subject
    else:
        return "No query parameters provided"
    
    main_url = api_url + query_str + "&api_key=" + str(SPRINGER_API_KEY)
    print("Full URL: ", main_url)
    
    response = requests.get(main_url, headers=headers)
    print("Status: ", response.status_code)

    if response.status_code != 200:
        return "Error: " + str(response.status_code) + " - " + response.text

    data = response.json()
    # check for total number of records 
    total_records = int(data['result'][0]['total'])
    print("Total records: ", total_records)
    current_records = 0
    while current_records < total_records:
        # check if nextPage exists
        try:
            if 'nextPage' in data:
                next_page_url = "http://api.springernature.com" + data['nextPage']
            else:
                next_page_url = None

            # multi-process all records in current page
            with concurrent.futures.ProcessPoolExecutor() as executor:
                results = [executor.submit(downloadPDFSpringer, record, directory) for record in data['records']]
                for f in concurrent.futures.as_completed(results):
                    print(f.result())

            # update current records count
            current_records += int(len(data['records']))

            # if next page exists, update next page url and call the API again
            if next_page_url:
                # API key is already present in the URL
                response = requests.get(next_page_url, headers=headers)
                if response.status_code != 200:
                    return "Error in next page: " + str(response.status_code) + " - " + response.text
                
                data = response.json()
        except Exception as e:
            print(e)

    print("Course name: ", course_name)
    # prep payload for beam ingest
    ingest_data = []
    
    # upload files to S3 bucket
    for file in os.listdir(directory):
        doi = file[:-4]
        doi = doi.replace("_", "/")
        doi_link = f"https://doi.org/{doi}"
        data = {
            "course_name": course_name,
            "group": "springer_open",
            "s3_paths": "courses/" + course_name + "/" + file, # type: ignore
            "readable_filename": file,
            "base_url": "",
            "url": doi_link,
            "journal": "",
        }
        s3_path = "courses/" + course_name + "/" + file # type: ignore
        s3_client.upload_file(directory + "/" + file, aws_bucket, s3_path)  # type: ignore
        ingest_data.append(data)
    
    # save ingest data to csv
    ingest_df = pd.DataFrame(ingest_data)
    csv_file = "publications_data.csv"
    if not os.path.exists(csv_file):
        ingest_df.to_csv(csv_file, index=False)
    else:
        ingest_df.to_csv(csv_file, mode='a', header=False, index=False)


    # call ingest
    beam_url = "https://41kgx.apps.beam.cloud"
    headers = {
    "Content-Type": "application/json",
    "Authorization": "Basic " + os.getenv('BEAM_AUTH_TOKEN')    # type: ignore
    }
    for data in ingest_data:
        payload = json.dumps(data)
        response = requests.post(beam_url, headers=headers, data=payload)
        if response.status_code == 200:
            print("Task status retrieved successfully!")
        else:
            print(f"Error: {response.status_code}. {response.text}")

    # Delete files from local directory
    shutil.rmtree(directory)
                                
    return "success"

def downloadPDFSpringer(record: dict, directory: str):
    """
    This function takes a record from the Springer API response and downloads the PDF file.
    It is called in a multi-process loop in downloadSpringerFulltext().
    Args:
        record: dictionary containing DOI and other metadata
        directory: local directory to save the files
    """
    headers = {'Accept': 'application/json'}

    if len(record['url']) < 1:
        return "No download link found for DOI: " + record['doi']

    # extract URL
    url = record['url'][0]['value'] + "?api_key=" + str(SPRINGER_API_KEY)
    url_response = requests.get(url, headers=headers)
    if url_response.status_code != 200:
        return "Error in accessing article link: " + str(url_response.status_code) + " - " + url_response.text
    url_data = url_response.json()

    # extract PDF link
    pdf_link = None
    links = url_data['link']
    for link in links:
        if link['content-type'] == 'application/pdf' and link['intended-application'] == 'text-mining':
            pdf_link = link['URL']
            #print("PDF Link: ", pdf_link)
            break
    if not pdf_link:
        return "No PDF link found for DOI: " + record['doi']
    
    # download PDF
    filename = record['doi'].replace("/", "_")
    if filename in ['10.1186_2196-5641-1-1', '10.1186_s40538-014-0009-x']:
        return "Skipping: " + filename
    try:
        response = requests.get(pdf_link)
        if response.status_code != 200:
            return "Error in downloading PDF: " + str(response.status_code) + " - " + response.text
        
        with open(directory + "/" + filename + ".pdf", "wb") as f:  # Open a file in binary write mode ("wb")
            for chunk in response.iter_content(chunk_size=1024):  # Download in chunks
                f.write(chunk)
        print("Downloaded: ", filename)
        return "success"
    except Exception as e:
        return "Error in downloading PDF: " + str(e)


def downloadWileyFulltext(course_name=None, issn=None):
    """
    This function fetches metadata from Crossref and downloads 
    full-text articles from a given journal from Wiley.
    """
    # create directory to store files
    directory = os.path.join(os.getcwd(), 'wiley_papers')
    if not os.path.exists(directory):
        os.makedirs(directory)

    api_key = os.environ.get("WILEY_TDM_TOKEN")
    metadata = []

    # get journal metadata
    journals = Journals()
    works = journals.works(issn=issn)
    count = 0
    for item in works:
        open_access = True
        count += 1
        article_metadata = {}
        # check if the license is open access - variant of CC
        if 'license' not in item:
            continue
            
        for license in item['license']:
            print("License URL: ", license['URL'])
            if license['URL'] in LICENSES:
                if LICENSES[license['URL']] == "closed_access":
                    #print("Article is not open access: ", item['DOI'])
                    open_access = False
                else:
                    print("Article is open access: ", item['DOI'])
                    article_metadata['license'] = LICENSES[license['URL']]
                    article_metadata['license_link'] = license['URL']
            else:
                article_metadata['license_link'] = license['URL']
            
        if not open_access:
            continue

        article_metadata['doi'] = item['DOI']
        article_metadata['title'] = item['title'][0]
        article_metadata['journal'] = item['container-title'][0]
        article_metadata['publisher'] = item['publisher']
        article_metadata['issn'] = item['ISSN'][0]
        article_metadata['url'] = item['URL']
        article_metadata['filename'] = item['DOI'].replace("/", "_") + ".pdf"

        print("Article Metadata: ", article_metadata)

        # download PDF based on doi
        download_status = downloadWileyPDF(item['DOI'])
        print("Download status: ", download_status)
        metadata.append(article_metadata)
    
    print("Download complete.")
    print("Total articles: ", count)
    metadata_csv = "wiley_metadata.csv"
    metadata_df = pd.DataFrame(metadata)
    if not os.path.exists(metadata_csv):
        metadata_df.to_csv(metadata_csv, index=False)
    else:
        metadata_df.to_csv(metadata_csv, mode='a', header=False, index=False)
    # prep payload for beam ingest
    # ingest_data = []
        
    # # upload files to S3 bucket
    # for file in os.listdir(directory):
    #     doi = file[:-4]
    #     doi = doi.replace("_", "/")
    #     doi_link = f"https://doi.org/{doi}"
    #     data = {
    #         "course_name": course_name,
    #         "group": "wiley",
    #         "s3_paths": "courses/" + course_name + "/" + file, # type: ignore
    #         "readable_filename": file,
    #         "base_url": "",
    #         "url": doi_link,
    #         "journal": "",
    #     }
    #     s3_path = "courses/" + course_name + "/" + file # type: ignore
    #     s3_client.upload_file(directory + "/" + file, aws_bucket, s3_path)  # type: ignore
    #     ingest_data.append(data)
        
    # # save ingest data to csv
    # ingest_df = pd.DataFrame(ingest_data)
    # csv_file = "publications_data.csv"
    # if not os.path.exists(csv_file):
    #     ingest_df.to_csv(csv_file, index=False)
    # else:
    #     ingest_df.to_csv(csv_file, mode='a', header=False, index=False)


    # # call ingest
    # beam_url = "https://41kgx.apps.beam.cloud"
    # headers = {
    # "Content-Type": "application/json",
    # "Authorization": "Basic " + os.getenv('BEAM_AUTH_TOKEN')    # type: ignore
    # }
    # for data in ingest_data:
    #     payload = json.dumps(data)
    #     response = requests.post(beam_url, headers=headers, data=payload)
    #     if response.status_code == 200:
    #         print("Task status retrieved successfully!")
    #     else:
    #         print(f"Error: {response.status_code}. {response.text}")

    # Delete files from local directory
    #shutil.rmtree(directory)
                

def downloadWileyPDF(doi=None):
    """
    This function downloads a PDF file from Wiley based on the DOI.
    """
    # create directory to store files
    directory = os.path.join(os.getcwd(), 'wiley_papers')
    if not os.path.exists(directory):
        os.makedirs(directory)

    api_key = os.environ.get("WILEY_TDM_TOKEN")

    # download PDF based on doi
    base_url = "https://api.wiley.com/onlinelibrary/tdm/v1/articles/"
    url = base_url + str(doi)
    print("URL: ", url)

    headers = {
        'Wiley-TDM-Client-Token': api_key,
        'Content-Type': 'application/json'
    }
    time.sleep(3)
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return "Error in accessing article link: " + str(response.status_code) + " - " + response.text
        
    filename = str(doi).replace("/", "_") + ".pdf"
    with open(directory + "/" + filename, "wb") as f:  # Open a file in binary write mode ("wb")
        for chunk in response.iter_content(chunk_size=1024):  # Download in chunks
            f.write(chunk)
    print("Downloaded: ", filename)
    
    return "success"


def downloadWileyArticle(doi=None):
    """
    This function fetches metadata from Crossref and downloads open access full text articles from Wiley.
    """
    # create directory to store files
    directory = os.path.join(os.getcwd(), 'wiley_papers')
    if not os.path.exists(directory):
        os.makedirs(directory)

    api_key = os.environ.get("WILEY_TDM_TOKEN")
    metadata = {}
    
    # get metadata from Crossref
    if doi:
        # get article metadata
        works = Works()
        article_data = works.doi(doi)
        print("Article license: ", article_data['license'])
        
        article_licenses = []
        
        for item in article_data['license']:
            article_licenses.append(item['URL'])
        print("Licenses: ", article_licenses)
        # check if the license is open access - variant of CC
        for license in article_licenses:
            if license in LICENSES:
                print("License found: ", license)
                if LICENSES[license] == "closed_access":
                    return "Article is not open access."
                else:
                    metadata['license'] = LICENSES[license]
                    break
            else:
                return "License not found."
        
        metadata['doi'] = doi
        metadata['title'] = article_data['title'][0]
        metadata['journal'] = article_data['container-title'][0]
        metadata['publisher'] = article_data['publisher']
        metadata['issn'] = article_data['ISSN'][0]
        metadata['url'] = article_data['URL']

        print("Metadata: ", metadata)

        # download PDF based on doi
        base_url = "https://api.wiley.com/onlinelibrary/tdm/v1/articles/"
        url = base_url + str(doi)

        print("URL: ", url)

        headers = {
            'Wiley-TDM-Client-Token': api_key,
            'Content-Type': 'application/json'
        }

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return "Error in accessing article link: " + str(response.status_code) + " - " + response.text
        
        filename = str(doi).replace("/", "_")
        with open(directory + "/" + filename + ".pdf", "wb") as f:  # Open a file in binary write mode ("wb")
            for chunk in response.iter_content(chunk_size=1024):  # Download in chunks
                f.write(chunk)
        print("Downloaded: ", filename)

        # upload file to S3 bucket

        # prep payload for beam ingest

        return "success"