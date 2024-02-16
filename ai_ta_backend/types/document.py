from pydantic import BaseModel, Field


class MaterialDocument(BaseModel):
  course_name: str
  readable_filename: str
  s3_path: str
  base_url: str = Field(default='')
  url: str = Field(default='')
  tag: str = Field(default='')
