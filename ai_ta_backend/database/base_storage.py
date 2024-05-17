from abc import ABC, abstractmethod

class BaseStorageDatabase(ABC):
  @abstractmethod
  def upload_file(self, file_path: str, bucket_name: str, object_name: str):
    pass
  @abstractmethod
  def download_file(self, object_name: str, bucket_name: str, file_path: str):
    pass
  @abstractmethod
  def delete_file(self, bucket_name: str, s3_path: str):
    pass
  @abstractmethod
  def generatePresignedUrl(self, object: str, bucket_name: str, s3_path: str, expiration: int = 3600):
    pass