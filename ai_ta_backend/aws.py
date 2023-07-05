
import glob 
import boto3 
import os 
import sys 
from multiprocessing.pool import ThreadPool 
import pathlib

def upload_data_files_to_s3(course_name:str, localdir:str):
    # target location of the files on S3  

    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME') 
    S3_FOLDER_NAME = "operations-management-organization-and-analysis"
    # Enter your own credentials file profile name below

    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        # aws_session_token=,  # Comment this line if not using temporary credentials
    )

    # Source location of files on local system 

    # The list of files we're uploading to S3 
    print(localdir)
    # filenames =  glob.glob(localdir, recursive=True) 

    filenames = []
    for root, subdirs, files in os.walk(localdir):
      for filename in files:
        filenames.append(os.path.join(root, filename))
    print(filenames)
    def upload(myfile): 
        print("hello!!")
        s3_file = f"{course_name}/{os.path.basename(myfile)}" 

        results = s3.upload_file(myfile, S3_BUCKET_NAME, s3_file) 
        print(results)

    # Number of pool processes is a guestimate - I've set 
    # it to twice number of files to be processed 

    # pool = ThreadPool(processes=len(filenames)*2) 
    pool = ThreadPool(processes=2) 
    

    pool.map(upload, filenames) 

    

    print("All Data files uploaded to S3 Ok")


