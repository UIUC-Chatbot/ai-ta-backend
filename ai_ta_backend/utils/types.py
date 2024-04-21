import datetime
from typing import Any, Dict, Optional

import pydantic


class DocumentMetadata(pydantic.BaseModel):
  authors: list[str]
  journal_name: str
  publication_date: datetime.date  # Changed from datetime.date to str
  keywords: list[str]
  doi: str
  title: str
  subtitle: Optional[str]
  visible_urls: list[str]
  field_of_science: str
  concise_summary: str
  specific_questions_document_can_answer: list[str]
  additional_fields: Optional[Dict[str, Any]] = {}

  # Can't get this to work properly
  # class Config:
  #     extra = pydantic.Extra.allow  # Allow arbitrary additional fields


# Prisma data model https://prisma-client-py.readthedocs.io/en/stable/
# TBH I'd rather invest in learning real SQL. Theo switched from Drizzle to Prisma... no long-term security in either.
# model DocumentMetadata {
#   id                             Int      @id @default(autoincrement())
#   authors                        String[]
#   journalName                    String
#   publicationDate                DateTime
#   keywords                       String[]
#   doi                            String
#   title                          String
#   subtitle                       String?   // Optional field
#   visibleUrls                    String[]
#   fieldOfScience                 String
#   conciseSummary                 String
#   specificQuestionsDocumentCanAnswer String[]
# }
