import os
import uuid
import zipfile
import io
import pandas as pd
import supabase
import sentry_sdk
import boto3
import botocore
from concurrent.futures import ProcessPoolExecutor
import requests
import json
from ai_ta_backend.emails import send_email

# Initialize Supabase client
SUPABASE_CLIENT = supabase.create_client(supabase_url=os.getenv('SUPABASE_URL'),  # type: ignore
                                        supabase_key=os.getenv('SUPABASE_API_KEY'))  # type: ignore


def export_documents_json(course_name: str, from_date='', to_date=''):
  """
  This function exports the documents to a json file.
  1. If the number of documents is greater than 1000, it calls a background task to upload the documents to S3.
  2. If the number of documents is less than 1000, it fetches the documents and zips them.
  Args:
      course_name (str): The name of the course.
      from_date (str, optional): The start date for the data export. Defaults to ''.
      to_date (str, optional): The end date for the data export. Defaults to ''.
  """ 

  if from_date != '' and to_date != '':
    # query between the dates
    print("from_date and to_date")
    response = SUPABASE_CLIENT.table("documents").select("id", count='exact').eq("course_name", course_name).gte(
        'created_at', from_date).lte('created_at', to_date).order('id', desc=False).execute()

  elif from_date != '' and to_date == '':
    # query from from_date to now
    print("only from_date")
    response = SUPABASE_CLIENT.table("documents").select("id", count='exact').eq("course_name", course_name).gte(
        'created_at', from_date).order('id', desc=False).execute()

  elif from_date == '' and to_date != '':
    # query from beginning to to_date
    print("only to_date")
    response = SUPABASE_CLIENT.table("documents").select("id", count='exact').eq("course_name", course_name).lte(
        'created_at', to_date).order('id', desc=False).execute()

  else:
    # query all data
    print("No dates")
    response = SUPABASE_CLIENT.table("documents").select("id",
                                                         count='exact').eq("course_name",
                                                                           course_name).order('id',
                                                                                              desc=False).execute()

  # add a condition to route to direct download or s3 download
  if response.count > 1000:
    # call background task to upload to s3
    
    filename = course_name + '_' + str(uuid.uuid4()) + '_documents.zip'
    s3_filepath = s3_file = f"courses/{course_name}/{filename}"
    # background task of downloading data - map it with above ID
    executor = ProcessPoolExecutor()
    executor.submit(export_data_in_bg, response, "documents", course_name, s3_filepath)
    return {"response": 'Download from S3', "s3_path": s3_filepath}

  else:
    # Fetch data
    if response.count > 0:
      # batch download
      total_doc_count = response.count
      first_id = response.data[0]['id']
      last_id = response.data[-1]['id']

      print("total_doc_count: ", total_doc_count)
      print("first_id: ", first_id)
      print("last_id: ", last_id)
      
      curr_doc_count = 0
      filename = course_name + '_' + str(uuid.uuid4()) + '_documents.json'
      file_path = os.path.join(os.getcwd(), filename)
          
      while curr_doc_count < total_doc_count:
        print("Fetching data from id: ", first_id)
        response = SUPABASE_CLIENT.table("documents").select("*").eq("course_name", course_name).gte('id', first_id).order('id', desc=False).limit(100).execute()
        df = pd.DataFrame(response.data)
        curr_doc_count += len(response.data)
              
        # writing to file
        if not os.path.isfile(file_path):
          df.to_json(file_path, orient='records')
        else:
          df.to_json(file_path, orient='records', lines=True, mode='a')

        if len(response.data) > 0:
          first_id = response.data[-1]['id'] + 1
          
      # Download file
      try:
        # zip file
        zip_filename = filename.split('.')[0] + '.zip'
        zip_file_path = os.path.join(os.getcwd(), zip_filename)

        with zipfile.ZipFile(zip_file_path, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
          zipf.write(file_path, filename)

        os.remove(file_path)
        return {"response": (zip_file_path, zip_filename, os.getcwd())}
      except Exception as e:
        print(e)
        sentry_sdk.capture_exception(e)
        return {"response": "Error downloading file."}
    else:
      return {"response": "No data found between the given dates."}
  

def export_data_in_bg(response, download_type, course_name, s3_path):
  """
  This function is called in export_documents_csv() to upload the documents to S3.
  1. download the documents in batches of 100 and upload them to S3.
  2. generate a pre-signed URL for the S3 file.
  3. send an email to the course admins with the pre-signed URL.

  Args:
      response (dict): The response from the Supabase query.
      download_type (str): The type of download - 'documents' or 'conversations'.
      course_name (str): The name of the course.
      s3_path (str): The S3 path where the file will be uploaded.
  """
  total_doc_count = response.count
  first_id = response.data[0]['id']
  print("total_doc_count: ", total_doc_count)
  print("pre-defined s3_path: ", s3_path)

  curr_doc_count = 0
  filename = s3_path.split('/')[-1].split('.')[0] + '.json'
  file_path = os.path.join(os.getcwd(), filename)

  # download data in batches of 100
  while curr_doc_count < total_doc_count:
    print("Fetching data from id: ", first_id)
    if download_type == 'documents':
      response = SUPABASE_CLIENT.table("documents").select("*").eq("course_name", course_name).gte('id', first_id).order('id', desc=False).limit(100).execute()
    else:
      response = SUPABASE_CLIENT.table("llm-convo-monitor").select("*").eq("course_name", course_name).gte('id', first_id).order('id', desc=False).limit(100).execute()
    df = pd.DataFrame(response.data)
    curr_doc_count += len(response.data)
            
    # writing to file
    if not os.path.isfile(file_path):
      df.to_json(file_path, orient='records')
    else:
      df.to_json(file_path, orient='records', lines=True, mode='a')

    if len(response.data) > 0:
      first_id = response.data[-1]['id'] + 1
  
  # zip file
  zip_filename = filename.split('.')[0] + '.zip'
  zip_file_path = os.path.join(os.getcwd(), zip_filename)

  with zipfile.ZipFile(zip_file_path, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
    zipf.write(file_path, filename)

  print("zip file created: ", zip_file_path)

  try:
    # upload to S3
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    )

    #s3_file = f"courses/{course_name}/exports/{os.path.basename(zip_file_path)}"
    s3_file = f"courses/{course_name}/{os.path.basename(zip_file_path)}"
    s3.upload_file(zip_file_path, os.getenv('S3_BUCKET_NAME'), s3_file)
    
    # remove local files
    os.remove(file_path)
    os.remove(zip_file_path)

    print("file uploaded to s3: ", s3_file)

    # pre-signed URL
    s3_object = s3.head_object(Bucket=os.getenv('S3_BUCKET_NAME'), Key=s3_path)
    
    # generate presigned URL
    s3_url = s3.generate_presigned_url('get_object', Params={'Bucket': os.getenv('S3_BUCKET_NAME'), 'Key': s3_path}, ExpiresIn=3600)
      
    # get admin email IDs
    headers = {
              "Authorization": f"Bearer {os.getenv('VERCEL_READ_ONLY_API_KEY')}",
              "Content-Type": "application/json"
          }
    
    hget_url = str(os.getenv('VERCEL_BASE_URL')) + "course_metadatas/" + course_name
    response = requests.get(hget_url, headers=headers)
    course_metadata = response.json()
    course_metadata = json.loads(course_metadata['result'])
    admin_emails = course_metadata['course_admins']
    bcc_emails = []

    # check for Kastan's email and move to bcc
    if 'kvday2@illinois.edu' in admin_emails:
      admin_emails.remove('kvday2@illinois.edu')
      bcc_emails.append('kvday2@illinois.edu')

    # add course owner email to admin_emails
    admin_emails.append(course_metadata['course_owner'])
    admin_emails = list(set(admin_emails))
    print("admin_emails: ", admin_emails)
    print("bcc_emails: ", bcc_emails)

    # add a check for emails, don't send email if no admin emails
    if len(admin_emails) == 0:
      return "No admin emails found. Email not sent."

    # send email to admins
    subject = "UIUC.chat Data Export Complete for " + course_name
    body_text = "The data export for " + course_name + " is complete.\n\nYou can download the file from the following link: \n\n" + s3_url + "\n\nThis link will expire in 48 hours."
    email_status = send_email(subject, body_text, os.getenv('EMAIL_SENDER'), admin_emails, bcc_emails)
    print("email_status: ", email_status)

    return "File uploaded to S3. Email sent to admins."

  except Exception as e:
    print(e)
    return "Error: " + str(e)

def check_s3_path_and_download(s3_path):
  """
  This function checks if the file exists in S3 and downloads it.
  Args:
      s3_path (str): The S3 path of the file.
  """
  s3 = boto3.client(
      's3',
      aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
  )

  try:
    print("Checking if file exists in S3...", s3_path)
    s3_object = s3.head_object(Bucket=os.getenv('S3_BUCKET_NAME'), Key=s3_path)
  
    # generate presigned URL
    s3_url = s3.generate_presigned_url('get_object', Params={'Bucket': os.getenv('S3_BUCKET_NAME'), 'Key': s3_path}, ExpiresIn=172800)
    print("Presigned URL: ", s3_url)
    return {"response": s3_url}  
                           
  except botocore.exceptions.ClientError as e:
    if e.response['Error']['Code'] == "404":
      # The object does not exist.
      return {"response": "Export is not complete yet. Please try again later."}
    else:
      # Something else has gone wrong.
      sentry_sdk.capture_exception(e)
      return {"response": "Error downloading file."}
      

def export_convo_history_json(course_name: str, from_date='', to_date=''):
  """
  This function exports the conversation history to a csv file.
  Args:
      course_name (str): The name of the course.
      from_date (str, optional): The start date for the data export. Defaults to ''.
      to_date (str, optional): The end date for the data export. Defaults to ''.
  """
  print("Exporting conversation history to csv file...")
  
  if from_date == '' and to_date == '':
    # Get all data
    print("No dates")
    response = SUPABASE_CLIENT.table("llm-convo-monitor").select("id", count='exact').eq(
        "course_name", course_name).order('id', desc=False).execute()
  elif from_date != '' and to_date == '':
    print("only from_date")
    # Get data from from_date to now
    response = SUPABASE_CLIENT.table("llm-convo-monitor").select("id", count='exact').eq(
        "course_name", course_name).gte('created_at', from_date).order('id', desc=False).execute()
  elif from_date == '' and to_date != '':
    print("only to_date")
    # Get data from beginning to to_date
    response = SUPABASE_CLIENT.table("llm-convo-monitor").select("id", count='exact').eq(
        "course_name", course_name).lte('created_at', to_date).order('id', desc=False).execute()
  else:
    print("both from_date and to_date")
    # Get data from from_date to to_date
    response = SUPABASE_CLIENT.table("llm-convo-monitor").select("id", count='exact').eq(
        "course_name", course_name).gte('created_at', from_date).lte('created_at', to_date).order('id',
                                                                                                  desc=False).execute()
  
  if response.count > 1000:
    # call background task to upload to s3
    filename = course_name + '_' + str(uuid.uuid4()) + '_convo_history.zip'
    s3_filepath = s3_file = f"courses/{course_name}/{filename}"
    # background task of downloading data - map it with above ID
    executor = ProcessPoolExecutor()
    executor.submit(export_data_in_bg, response, "conversations", course_name, s3_filepath)
    return {"response": 'Download from S3', "s3_path": s3_filepath}

  # Fetch data
  if response.count > 0:
    print("id count greater than zero")
    first_id = response.data[0]['id']
    last_id = response.data[-1]['id']
    total_count = response.count

    filename = course_name + '_' + str(uuid.uuid4()) + '_convo_history.csv'
    file_path = os.path.join(os.getcwd(), filename)
    curr_count = 0
    # Fetch data in batches of 25 from first_id to last_id
    while curr_count < total_count:
      print("Fetching data from id: ", first_id)
      response = SUPABASE_CLIENT.table("llm-convo-monitor").select("*").eq("course_name", course_name).gte(
          'id', first_id).lte('id', last_id).order('id', desc=False).limit(25).execute()
      # Convert to pandas dataframe
      df = pd.DataFrame(response.data)
      curr_count += len(response.data)

      # Append to csv file
      if not os.path.isfile(file_path):
        df.to_json(file_path, orient='records', lines=True)
      else:
        df.to_json(file_path, orient='records', lines=True, mode='a')

      # Update first_id
      if len(response.data) > 0:
        first_id = response.data[-1]['id'] + 1
        print("updated first_id: ", first_id)

    # Download file
    try:
      # zip file
      zip_filename = filename.split('.')[0] + '.zip'
      zip_file_path = os.path.join(os.getcwd(), zip_filename)

      with zipfile.ZipFile(zip_file_path, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(file_path, filename)
      os.remove(file_path)

      return {"response": (zip_file_path, zip_filename, os.getcwd())}
    except Exception as e:
      print(e)
      sentry_sdk.capture_exception(e)
      return {"response": "Error downloading file!"}
  else:
    return {"response": "No data found between the given dates."}
