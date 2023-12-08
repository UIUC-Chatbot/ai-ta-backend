import os
from multiprocessing import Lock, cpu_count
from multiprocessing.pool import ThreadPool
from typing import List, Optional

import boto3


def upload_data_files_to_s3(course_name: str, localdir: str) -> Optional[List[str]]:
  """Uploads all files in localdir to S3 bucket.

  Args:
    course_name (str): Official course name on our website. 
    localdir (str): Local directory to upload from, coursera-dl downloads to this directory. 

  Returns:
    Optional[List[str]]: A list of S3 paths, the final resting place of uploads, or None if no files were uploaded.
  """
  s3 = boto3.client(
      's3',
      aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
  )

  filenames = []
  for root, _subdirs, files in os.walk(localdir):
    for filename in files:
      filenames.append(os.path.join(root, filename))

  if not filenames:
    print(f"No files to upload. Not found in: {localdir}")
    return None

  print(f"Files to upload: {filenames}")
  print("About to upload...")

  s3_paths = []
  s3_paths_lock = Lock()

  def upload(myfile):
    s3_file = f"courses/{course_name}/{os.path.basename(myfile)}"
    s3.upload_file(myfile, os.getenv('S3_BUCKET_NAME'), s3_file)
    with s3_paths_lock:
      s3_paths.append(s3_file)

  # only 2 parallel uploads because we're getting rate limited with min_p=6... 503 errors.
  min_p = 2
  max_p = cpu_count()
  num_procs = max(min(len(filenames), max_p), min_p)
  pool = ThreadPool(processes=num_procs)
  pool.map(upload, filenames)

  print("All data files uploaded to S3 successfully.")
  return s3_paths


if __name__ == '__main__':
  pass
