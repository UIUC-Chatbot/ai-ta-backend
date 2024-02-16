from pydantic import BaseModel, Field


class Document(BaseModel):
  course_name: str
  readable_filename: str
  s3_path: str
  base_url: str = Field(default='')
  url: str = Field(default='')
  doc_group: str = Field(default='')
