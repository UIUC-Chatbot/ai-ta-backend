import os
import uuid
import zipfile

import pandas as pd
import supabase
import sentry_sdk

# Initialize Supabase client
SUPABASE_CLIENT = supabase.create_client(supabase_url=os.getenv('SUPABASE_URL'),  # type: ignore
                                        supabase_key=os.getenv('SUPABASE_API_KEY'))  # type: ignore


def export_documents_csv(course_name: str, from_date='', to_date=''):
  """
  This function exports the documents to a csv file.
  Args:
      course_name (str): The name of the course.
      from_date (str, optional): The start date for the data export. Defaults to ''.
      to_date (str, optional): The end date for the data export. Defaults to ''.
  """
  print("Exporting documents to csv file...")
  print("course_name: ", course_name)
  print("from_date: ", from_date)
  print("to_date: ", to_date)
  

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

  # Fetch data
  if response.count > 0:
    # batch download
    total_doc_count = response.count
    first_id = response.data[0]['id']
    last_id = response.data[-1]['id']

    print("total_doc_count: ", total_doc_count)
    print("first_id: ", first_id)
    print("last_id: ", last_id)
    
    # make directory
    # if not os.path.exists('exported_files'):
    #   os.makedirs('exported_files')
    
    curr_doc_count = 0
    filename = course_name + '_' + str(uuid.uuid4()) + '_documents.json'
    file_path = os.path.join(os.getcwd(), filename)
    files_created = []
    files_created.append(file_path)
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

      #print("len: ", len(response.data))
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
      return (zip_file_path, zip_filename, os.getcwd())
    except Exception as e:
      print(e)
      sentry_sdk.capture_exception(e)
      return "Error downloading file"
  else:
    return "No data found between the given dates."


def export_convo_history_csv(course_name: str, from_date='', to_date=''):
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

      return (zip_file_path, zip_filename, os.getcwd())
    except Exception as e:
      print(e)
      sentry_sdk.capture_exception(e)
      return "Error downloading file"
  else:
    return "No data found between the given dates."
