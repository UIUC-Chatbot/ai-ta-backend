import os
import pytest
from unittest.mock import patch, MagicMock
from .aws import AWSStorage
from dotenv import load_dotenv

load_dotenv()

@pytest.fixture
def aws_storage():
    with patch('boto3.client') as mock_boto_client:
        mock_s3_client = MagicMock()
        mock_boto_client.return_value = mock_s3_client
        storage = AWSStorage()
        yield storage, mock_s3_client

def test_init(aws_storage):
    storage, mock_s3_client = aws_storage
    assert storage.s3_client == mock_s3_client

def test_upload_file(aws_storage):
    storage, mock_s3_client = aws_storage
    file_path = "../test-docs/3.pdf"
    bucket_name = os.environ['S3_BUCKET_NAME']
    object_name = "courses/test-project-asmita/3.pdf"

    storage.upload_file(file_path, bucket_name, object_name)
    mock_s3_client.upload_file.assert_called_once_with(file_path, bucket_name, object_name)

def test_download_file(aws_storage):
    storage, mock_s3_client = aws_storage
    file_path = "3.pdf"
    bucket_name = os.environ['S3_BUCKET_NAME']
    object_name = "courses/test-project-asmita/3.pdf"

    storage.download_file(object_name, bucket_name, file_path)
    mock_s3_client.download_file.assert_called_once_with(bucket_name, object_name, file_path)