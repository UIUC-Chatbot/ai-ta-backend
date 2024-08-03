import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import traceback

from dotenv import load_dotenv
from minio import Minio  # type: ignore
from urllib3 import PoolManager
from urllib3.util.retry import Retry
from doc2json.grobid_client import GrobidClient
import urllib3
import tempfile

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv(override=True)

BUCKET_NAME = 'pubmed'
input_files = [
"00001-2022.PMC9108969.pdf",
"00002-2022.PMC9108967.pdf",
"00004-2022.PMC8994962.pdf",
"00004-2023.PMC10259823.pdf",
"00006-2022.PMC8899496.pdf",
"00007-2023.PMC10086694.pdf",
"00008-2022.PMC9379355.pdf",
"00009-2022.PMC9149393.pdf",
"0001.f1.pdf",
"0001.f2.pdf",
"00010-2022.PMC9059131.pdf",
"00010-2023.PMC10277870.pdf",
"00011-2023.PMC10204863.pdf",
# "00012-2022.PMC9101655.pdf",
"00013-2023.PMC10204849.pdf",
# "00014-2022.PMC8841010.pdf",
"00016-2022.PMC9124870.pdf",
"00017-2022.PMC8995535.pdf",
"00017-2023.PMC10423983.pdf",
"00020-2023.PMC10204814.pdf",
"00021-2023.pdf",
"00024-2022.PMC9574553.pdf",
"00024-2023.PMC10316040.pdf",
"00027-2023.PMC10440677.pdf",
"00028-2022.PMC9234436.pdf",
"00030-2022.PMC9339768.pdf",
"00031-2022.PMC9062297.pdf",
]

# Create a custom PoolManager with desired settings
http_client = PoolManager(
    timeout=300,  # 5 minutes timeout
    maxsize=200,  # Increased pool size
    retries=Retry(total=10, backoff_factor=0.1, status_forcelist=[100, 102, 103, 104]))

minio_client = Minio(
    os.environ['MINIO_API_ENDPOINT'],
    access_key=os.getenv('MINIO_ACCESS_KEY'),
    secret_key=os.getenv('MINIO_SECRET_KEY'),
    secure=True,
    http_client=http_client,
)

grobid_server = os.getenv('GROBID_SERVER')
BASE_TEMP_DIR = 'temp'

def process_pdf(file_name):
    # Download file from Minio
    start_time_minio = time.monotonic()
    start_time_grobid = time.monotonic()
    response = minio_client.get_object(BUCKET_NAME, file_name)
    file_content = response.read()
    response.close()
    response.release_conn()
    print(f"⏰ Minio download: {(time.monotonic() - start_time_minio):.2f} seconds")

    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
        temp_pdf.write(file_content)
        temp_pdf_path = temp_pdf.name
    
    # Save to a persistent file
    persistent_path = os.path.join('grobid_speedtest_pdfs', file_name)
    os.makedirs(os.path.dirname(persistent_path), exist_ok=True)
    with open(persistent_path, 'wb') as persistent_pdf:
        persistent_pdf.write(file_content)

    # Create a temporary file for TEI output
    with tempfile.NamedTemporaryFile(delete=False, suffix='.tei.xml') as temp_tei:
        temp_tei_path = temp_tei.name

    # Configure Grobid
    grobid_config = {
        "grobid_server": grobid_server,
        "batch_size": 2000,
        "sleep_time": 5,
        "generateIDs": False,
        "consolidate_header": False,
        "consolidate_citations": False,
        "include_raw_citations": True,
        "include_raw_affiliations": False,
        "max_workers": 8,
        "concurrency": 8,
        "n": 8,
        "timeout": 600,
    }

    # Process PDF with Grobid
    client = GrobidClient(grobid_config)
    client.process_pdf(temp_pdf_path, temp_tei_path, "processFulltextDocument")

    # Clean up temporary files
    os.unlink(temp_pdf_path)
    os.unlink(temp_tei_path)
    print(f"📜 Grobid runtime: {(time.monotonic() - start_time_grobid):.2f} seconds")

    return f"Processed {file_name}"

def main():
    start_time = time.monotonic()

    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_pdf, file_name) for file_name in input_files]
        
        for future in as_completed(futures):
            try:
                result = future.result()
                print(result)
            except Exception as e:
                print(f"An error occurred: {str(e)}")
                traceback.print_exc()

    print(f"Total runtime: {(time.monotonic() - start_time) / 60:.2f} minutes")

if __name__ == "__main__":
    main()
