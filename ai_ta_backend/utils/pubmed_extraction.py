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

    gz_filepath = downloadXML(ftp_address, ftp_path, file_list[0], "pubmed")
    print("GZ Downloaded: ", gz_filepath)

    # extract the XML file
    xml_filepath = extractXMLFile(gz_filepath)
    print("XML Extracted: ", xml_filepath)

    xml_filepath = "pubmed/pubmed24n1219.xml"
    metadata = extractMetadataFromXML(xml_filepath)

    # find PMC ID and DOI for all articles
    metadata_with_ids = getArticleIDs(metadata)

    # download the articles
    complete_metadata = downloadArticles(metadata_with_ids)
    print("Complete metadata: ", complete_metadata)
    
    # upload articles to bucket
    article_upload = uploadToStorage("pubmed_abstracts")
    print("Uploaded articles: ", article_upload)

    # upload metadata to SQL DB
    response = SUPBASE_CLIENT.table("publications").upsert(complete_metadata).execute()
    print("Supabase response: ", response)
    exit()

    return "success"

def downloadXML(ftp_address: str, ftp_path: str, file: str, local_dir: str):
    """
    Downloads a .gz XML file from the FTP baseline folder and stores it in the local directory.
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
    return local_filepath

def getFileList(ftp_address: str, ftp_path: str, extension: str = ".gz"):
    """
    Returns a list of .gz files in the FTP folder.
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
    # create a directory to store abstracts
    os.makedirs("pubmed_abstracts", exist_ok=True)

    tree = ET.parse(xml_filepath)
    root = tree.getroot()
    metadata = []
    
    # Extract metadata from the XML file
    for item in root.iter('PubmedArticle'):
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
            continue

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
            article_data['published'] = f"{issue.find('PubDate/Year').text}-{issue.find('PubDate/Month').text}"
        elif issue.find('PubDate/Year') is not None:
            article_data['published'] = f"{issue.find('PubDate/Year').text}"
        else:
            article_data['published'] = None
        
        # extract and store abstract in a text file
        abstract = article.find('Abstract')
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
                if article_data['article_title']:
                    f.write("Article title: " + article_data['article_title'] + "\n")
                if article_data['journal_title']:
                    f.write("Journal title: " + article_data['journal_title'] + "\n")
                f.write("Abstract: " + abstract_text)
        
        # some articles are listed, but not released online yet. Adding fields for such articles to maintain uniformity.
        article_data['live'] = True
        article_data['release_date'] = None
        article_data['license'] = None
        article_data['pubmed_ftp_link'] = None
        article_data['filepath'] = abstract_filename

        metadata.append(article_data)
        if len(metadata) == 20:
            return metadata
    return metadata

def getArticleIDs(metadata: list):
    """
    Retrieves the PMC ID and DOI for given articles and updates the metadata.
    """
    base_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
    app_details = "?tool=ncsa_uiuc&email=caiincsa@gmail.com&format=json"

    batch_size = 200    # maximum number of articles API can process in one request
    for i in range(0, len(metadata), batch_size):
        batch = metadata[i:i+batch_size]
        ids = ",".join([article['pmid'] for article in batch])
        response = requests.get(base_url + app_details + "&ids=" + ids)
        data = response.json()        
        records = data['records']

        for record in records:
            if 'errmsg' in record:
                print("Error: ", record['errmsg'])
                for article in batch:
                    if article['pmid'] == record['pmid']:
                        article['live'] = False
                        break
                continue
            else:
                # find article with matching pmid and update pmcid, doi, live, and release date fields
                for article in batch:
                    if article['pmid'] == record['pmid']:
                        article['pmcid'] = record['pmcid']
                        article['doi'] = record['doi']
                        article['live'] = False if 'live' in record and record['live'] == "false" else True
                        article['release_date'] = record.get('release-date', article['release_date'])
                        print("Updated metadata in ID converter: ", article)
                        break
    return metadata

def downloadArticles(metadata: list):
    """
    Downloads articles from PMC and stores them in bucket.
    Updates metadata with license information.
    """

    base_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?"
    print("Downloading articles...")

    # connect to FTP server anonymously
    ftp = ftplib.FTP("ftp.ncbi.nlm.nih.gov")
    ftp.login()

    for article in metadata:

        if article['live'] is False or article['pmcid'] is None:
            continue
        
        # else proceed with download
        if article['pmcid']:
            # download the article
            final_url = base_url + "id=" + article['pmcid'] 
            print("Downloading: ", final_url)

            xml_response = requests.get(final_url)
            extracted_data = extractArticleData(xml_response.text)
            
            print("\nExtracted data: ", extracted_data)

            # if no data extracted (reason: article not released/open-access), skip to next article
            if not extracted_data:
                article['live'] = False
                continue

            # update metadata with license and ftp link information
            article['license'] = extracted_data[0]['license']
            article['pubmed_ftp_link'] = extracted_data[0]['href'] if 'href' in extracted_data[0] else None
            
            # download the article
            ftp_url = urlparse(extracted_data[0]['href'])
            ftp_path = ftp_url.path[1:]
            print("FTP path: ", ftp_path)

            filename = ftp_path.split("/")[-1]
            local_file = os.path.join("pubmed_abstracts", filename)
            with open(local_file, 'wb') as f:
                ftp.retrbinary('RETR ' + ftp_path, f.write)
            print("Downloaded: ", local_file)
            article['filepath'] = local_file

            # if file is .tar.gz, extract the PDF and delete the tar.gz file
            if filename.endswith(".tar.gz"):
                extracted_pdf_paths = extractPDF(local_file)
                print("Extracted PDF: ", extracted_pdf_paths)
                article['filepath'] = ",".join(extracted_pdf_paths)
                os.remove(local_file)
            
            print("\nUpdated metadata after download: ", article)
    ftp.login()
    return metadata          

def extractPDF(tar_gz_filepath: str):
    """
    Extracts the PDF file from the .tar.gz file.
    """
    print("Extracting PDF from: ", tar_gz_filepath)
    extracted_paths = []
    with tarfile.open(tar_gz_filepath, "r:gz") as tar:
        for member in tar:
            if member.isreg() and member.name.endswith(".pdf"):
                tar.extract(member, path="pubmed_abstracts")
                print("Extracted: ", member.name)
                extracted_paths.append(os.path.join("pubmed_abstracts", member.name))
              
    return extracted_paths

def extractArticleData(xml_string: str):
    """
    Extracts license information and article download link from the XML response.
    """
    root = ET.fromstring(xml_string)

    if root.find(".//error") is not None:
        return []

    records = root.findall(".//record")
    extracted_data = []
    href = None
    print("In extractArticleData")
    for record in records:
        record_id = record.get("id")
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

def uploadToStorage(filepath: str):
    """
    Uploads all files present in given folder to Minio bucket.
    """
    print("in uploadToStorage()")
    
    minio_client = Minio(os.environ['MINIO_URL'],
        access_key=os.environ['MINIO_ACCESS_KEY'],
        secret_key=os.environ['MINIO_SECRET_KEY'],
        secure=False
    )

    bucket_name = "pubmed"
    found = minio_client.bucket_exists(bucket_name)
    if not found:
        minio_client.make_bucket(bucket_name)
        print("Created bucket", bucket_name)
    else:
        print("Bucket", bucket_name, "already exists")

    for root, dirs, files in os.walk(filepath):
        # can parallelize this upload
        for file in files:
            file_path = os.path.join(root, file)
            object_name = file_path.split("/")[-1]
            # insert local file into remote bucket
            minio_client.fput_object(bucket_name, object_name, file_path)
            print("Uploaded: ", object_name)
    return "success"



        
                        



    
            




    
