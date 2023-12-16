import os
import uuid

import pandas as pd
import supabase
import sentry_sdk

def export_convo_history_csv(course_name: str, from_date='', to_date=''):
  """
  This function exports the conversation history to a csv file.
  Args:
      course_name (str): The name of the course.
      from_date (str, optional): The start date for the data export. Defaults to ''.
      to_date (str, optional): The end date for the data export. Defaults to ''.
  """
  print("Exporting conversation history to csv file...")
  supabase_client = supabase.create_client(  # type: ignore
      supabase_url=os.getenv('SUPABASE_URL'),  # type: ignore
      supabase_key=os.getenv('SUPABASE_API_KEY'))  # type: ignore

  if from_date == '' and to_date == '':
    # Get all data
    print("No dates")
    response = supabase_client.table("llm-convo-monitor").select("id", count='exact').eq(
        "course_name", course_name).order('id', desc=False).execute()
  elif from_date != '' and to_date == '':
    print("only from_date")
    # Get data from from_date to now
    response = supabase_client.table("llm-convo-monitor").select("id", count='exact').eq(
        "course_name", course_name).gte('created_at', from_date).order('id', desc=False).execute()
  elif from_date == '' and to_date != '':
    print("only to_date")
    # Get data from beginning to to_date
    response = supabase_client.table("llm-convo-monitor").select("id", count='exact').eq(
        "course_name", course_name).lte('created_at', to_date).order('id', desc=False).execute()
  else:
    print("both from_date and to_date")
    # Get data from from_date to to_date
    response = supabase_client.table("llm-convo-monitor").select("id", count='exact').eq(
        "course_name", course_name).gte('created_at', from_date).lte('created_at', to_date).order('id',
                                                                                                  desc=False).execute()

  # Fetch data
  if response.count > 0:
    print("id count greater than zero")
    first_id = response.data[0]['id']
    last_id = response.data[-1]['id']

    filename = course_name + '_' + str(uuid.uuid4()) + '_convo_history.csv'
    file_path = os.path.join(os.getcwd(), filename)
    # Fetch data in batches of 25 from first_id to last_id
    while first_id <= last_id:
      print("Fetching data from id: ", first_id)
      response = supabase_client.table("llm-convo-monitor").select("*").eq("course_name", course_name).gte(
          'id', first_id).lte('id', last_id).order('id', desc=False).limit(25).execute()
      # Convert to pandas dataframe
      df = pd.DataFrame(response.data)
      # Append to csv file
      if not os.path.isfile(file_path):
        df.to_csv(file_path, mode='a', header=True, index=False)
      else:
        df.to_csv(file_path, mode='a', header=False, index=False)

      # Update first_id
      first_id = response.data[-1]['id'] + 1
      print("updated first_id: ", first_id)

    # Download file
    try:
      return (file_path, filename, os.getcwd())
    except Exception as e:
      print(e)
      sentry_sdk.capture_exception(e)
      return "Error downloading file"
  else:
    return "No data found between the dates"
