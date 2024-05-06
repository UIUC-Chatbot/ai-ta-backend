import os
import json
import pandas as pd
import shutil
import requests
import supabase
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import concurrent.futures
from ai_ta_backend.database import aws, sql

SPRINGER_API_KEY = os.environ.get('SPRINGER_API_KEY')

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
