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
# from utils.logging_config import setup_detailed_logging

from ai_ta_backend.database.sql import SQLDatabase

# logger = setup_detailed_logging()

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
        # self.logger = logger
        # self.engine = engine
        self.sql_db = SQLDatabase()
        self.client = ChatOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o", temperature=0
        )
        self.extractor = create_extractor(
            self.client, tools=[DocumentMetadata], tool_choice="DocumentMetadata"
        )
    
    def process_documents(self, input_prompt: str) -> List[Dict[str, Any]]:
        """
        This function generates metadata from the text chunks and table JSONs extracted from the PDFs.
        """
        print("Input prompt: ", input_prompt)
        try:
            # code
            # fetch documents with chunk_status = completed and metadata_status = pending/failed
            chunks = self.sql_db.getCedarChunks().data

            # Group chunks by document_id
            from itertools import groupby
            from operator import itemgetter

            # Sort chunks by document_id to prepare for grouping
            sorted_chunks = sorted(chunks, key=itemgetter('document_id'))

            # Process each document's chunks
            for document_id, doc_chunks in groupby(sorted_chunks, key=itemgetter('document_id')):
                doc_chunks = list(doc_chunks)  # Convert iterator to list
                print(f"Processing document ID: {document_id}")
                
                # Separate table and content chunks
                table_chunks = [chunk for chunk in doc_chunks if chunk['chunk_type'] in ['Table', 'TableChunk']]
                content_chunks = [chunk for chunk in doc_chunks if chunk['chunk_type'] not in ['Table', 'TableChunk']]

                print(f"Table chunks: {len(table_chunks)}")
                print(f"Content chunks: {len(content_chunks)}")

                # Process content chunks in batches
                content_texts = [chunk['content'] for chunk in content_chunks]
                batch_size = 10
                existing_metadata = None

                # Create combined batch processing
                chunk_batches = (
                    # Process each table chunk individually
                    [
                        [
                            (
                                json.dumps(chunk['table_data'])
                                if chunk['table_data']
                                else chunk['table_html']
                            )
                        ]
                        for chunk in table_chunks
                    ]
                    +
                    # Process content chunks in batches
                    [
                        content_texts[i : i + batch_size]
                        for i in range(0, len(content_texts), batch_size)
                    ]
                )
                print(f"Total chunk batches: {len(chunk_batches)}")

                break
                
            return []
        except Exception as e:
            print("Error: ", e)
            # self.logger.error(f"Error processing documents: {e}")
            return []
