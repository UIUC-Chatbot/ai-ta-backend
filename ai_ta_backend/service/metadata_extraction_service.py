"""
Metadata extraction service for Cedar Bluff documents.
"""
import os 
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from trustcall import create_extractor
from utils.logging_config import setup_detailed_logging

logger = setup_detailed_logging()

class DocumentMetadata(BaseModel):
    """
    A generic nested structure for hierarchical metadata where:
    - First level represents the primary/parent entities
    - Second level represents logical groupings/categories
    - Third+ levels represent nested attributes and their values
    The structure is flexible and can accommodate any number of nesting levels.
    """

    data: Dict[str, Dict[str, Any]] = Field(
        description="Nested structure: parent_entity -> category -> nested_attributes"
    )

    class Config:
        extra = "allow"
        json_schema_extra = {
            "example": {
                "data": {
                    "parent_entity_1": {  # Top-level entity
                        "category_1": {  # Logical grouping
                            "attribute_1": "value_1",
                            "nested_group": {  # Can have deeper nesting
                                "sub_attribute": "value_2"
                            },
                        },
                        "category_2": {"attribute_2": "value_3"},
                    }
                }
            }
        }


class DocumentMetadataProcessor:
    def __init__(self, engine=None):
        self.logger = logger
        self.engine = engine
        self.client = ChatOpenAI(
            api_key=Field(os.getenv("OPENAI_API_KEY")), model="gpt-4o", temperature=0
        )
        self.extractor = create_extractor(
            self.client, tools=[DocumentMetadata], tool_choice="DocumentMetadata"
        )
    
    async def process_documents(self, input_prompt: str) -> List[Dict[str, Any]]:
        """
        This function generates metadata from the text chunks and table JSONs extracted from the PDFs.
        """
        print("Input prompt: ", input_prompt)
        
        return []
        
    

