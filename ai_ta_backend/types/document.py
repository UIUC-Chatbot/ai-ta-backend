from pydantic import BaseModel, Field
from typing import List

class MaterialDocument(BaseModel):
  course_name: str
  readable_filename: str
  s3_path: str
  base_url: str = Field(default='')
  url: str = Field(default='')
  doc_groups: List[str] = Field(default=[])