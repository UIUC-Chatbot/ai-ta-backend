import os
import shutil
import boto3
from ai_ta_backend.vector_database import Ingest
import hashlib
from ai_ta_backend.aws import upload_data_files_to_s3
from ai_ta_backend.vector_database import Ingest


def generate_checksum(file_path):
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as file:
        # Read and update the hash string value in blocks
        for byte_block in iter(lambda: file.read(4096), b""):
            md5_hash.update(byte_block)
    return md5_hash.hexdigest()

def update_files(source_path: str, course_name: str):
    """
    Compares and updates files in S3 and QDRANT
    Args:
        source_path: path to the directory containing the files to be uploaded
        course_name: name of the course whose files need to be updated
    To-do:
        1. Get S3 paths of files for given course_name
        2. Compute checksums of every file in source_path folder
        3. Compare checksums with S3 files - if different, upload to S3 and ingest into QDRANT
    """
    print("In update_files")

    ingester = Ingest()
    # Get S3 paths of files for given course_name
    s3_files = ingester.getAll(course_name)    

    # Access checksum of s3 files
    s3_client = boto3.client('s3', aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                             aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),)
    
    # Compute checksum of every file in source_path folder
    filenames = []
    for root, subdirs, files in os.walk(source_path):
        for file in files:
            print("file: ", file)
            filepath = os.path.join(root, file)
            file_checksum = generate_checksum(filepath)
    
        # compare file checksum with checksum of all s3 files
        for s3_file in s3_files:
            s3_path = s3_file['s3_path']
            s3_object = s3_client.get_object(Bucket=os.getenv('S3_BUCKET_NAME'), Key=s3_path)
            s3_checksum = s3_object['ETag']

            # remove file from the folder if checksums match
            if str(file_checksum) == s3_checksum[1:-1]:
                print("checksums match: ", file)
                os.remove(filepath)
                continue


    # Upload remaining files to S3 - canvas export contains subdirectories
    subdirectories = [subdir for subdir in os.listdir(source_path) if os.path.isdir(os.path.join(source_path, subdir))]
    print("subdirs: ", subdirectories)

    if len(subdirectories) == 0:
        # pass the source path
        new_s3_paths = upload_data_files_to_s3(course_name, source_path)
    else:
        # pass the subdirectory paths
        for subdir in subdirectories:
            subdir_path = os.path.join(source_path, subdir)
            if len(os.listdir(subdir_path)) == 0:
                continue
            print("subdir_path: ", subdir_path)
            new_s3_paths = upload_data_files_to_s3(course_name, subdir_path)
            subdir_ingest = ingester.bulk_ingest(new_s3_paths, course_name=course_name)
    
    # Delete files from local directory
    shutil.rmtree(source_path)

    return "Success"


    
