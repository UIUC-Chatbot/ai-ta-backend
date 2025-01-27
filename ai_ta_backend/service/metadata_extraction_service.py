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
from itertools import groupby
from operator import itemgetter
import asyncio
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

    def process_documents(self, input_prompt: str, document_ids: List) -> Dict[str, Any]:
        """
        This function generates metadata from the text chunks and table JSONs extracted from the PDFs.
        """
        print("Input prompt: ", input_prompt)
        try:
            async def process_batch(batch, existing_metadata, user_prompt):
                print(f"Processing batch...")
                output_format = """
                        {
                            "data": {
                                "<parent_entity>": {            # Primary/top-level entity identifier
                                    "<category>": {             # Logical grouping of related information
                                        "<attribute>": <value>   # Attribute-value pairs, can be nested further
                                    }
                                }
                            }
                        }
                """
                prompt = """You are an expert at analyzing documents and extracting structured metadata into clean, hierarchical formats.
                    Your task is to extract and organize all information into a nested structure that preserves relationships and values. 
                    Carefully structure the output to best respond to the user's request. 
                    Since information will be shared iteratively and your responses will be saved in existing metadata, feel free to restructure the output so that it is most useful to the user. 
                    This might be the case especially when there's lower level information that is not shared yet.

                    User Request: {user_prompt}

                    Important Instructions:
                        1. PARENT ENTITY IDENTIFICATION
                          - Identify the main top-level entities that serve as primary identifiers
                          - These group related information together at the highest level

                        2. CATEGORY IDENTIFICATION
                          - Identify distinct logical groups of information
                          - Each category should group related attributes together

                        3. VALUE MAPPING
                          - For each parent entity and category:
                            * Map every attribute to its exact value
                            * Keep text exactly as shown
                            * Preserve all formatting and units
                            * Maintain relationships between values

                        4. DATA QUALITY
                          - Preserve exact text and values
                          - Don't modify or summarize values
                          - Maintain all relationships and hierarchies
                          - Don't skip any information

                        Remember:
                        - Focus on preserving relationships and hierarchies
                        - Be thorough in extracting all relevant data
                        - Keep the structure consistent across all entries
                        - Allow for flexible nesting where needed

                        Critical Requirements:
                        - Preserve exact text and values
                        - Include all fields and values
                        - Maintain hierarchical relationships
                        - Keep formatting and units intact
                        - Don't skip any information
                        - Don't summarize or modify values
                        - Preserve all specifications, details, attributes, and relationships
                        - Do not make up any information, only extract what is present in the document or the existing metadata

                    Output Format: 
                """
                

                try:
                    prompt = prompt.format(user_prompt=user_prompt) + output_format # adding this way because including it in the main prompt gives formatting errors.
                    result = await self.extractor.ainvoke(
                        {
                            "messages": [
                                {"role": "system", "content": prompt},
                                {
                                    "role": "user",
                                    "content": "Extract structured tractor metadata with all models at the top level, and their components and attributes and their relationships in a nested structure:\n\n"
                                    + "\n\n Document Chunks: ".join(batch),
                                },
                            ],
                            "existing": (
                                {"DocumentMetadata": existing_metadata}
                                if existing_metadata
                                else None
                            ),
                        }
                    )
                    
                    if result:
                        metadata = DocumentMetadata(**result["responses"][0].model_dump())
                        return metadata
                except Exception as e:
                    print("Error processing batch:", e)
                    return None

            # Process each document's chunks
            curr_run_id = self.sql_db.getLastRunID().data[0]['run_id'] + 1
            print(f"Current run ID: {curr_run_id}")
            
            for document_id in document_ids:
                try:
                    # Fetch document chunks
                    doc_chunks = self.sql_db.getCedarChunks(document_id).data
                    if not doc_chunks:
                        print(f"No chunks found for document ID: {document_id}")
                        continue
                    
                    print(f"Processing document ID: {document_id}")
                    
                    table_chunks = [chunk for chunk in doc_chunks if chunk['chunk_type'] in ['Table', 'TableChunk']]
                    content_chunks = [chunk for chunk in doc_chunks if chunk['chunk_type'] not in ['Table', 'TableChunk']]

                    print(f"Table chunks: {len(table_chunks)}")
                    print(f"Content chunks: {len(content_chunks)}")

                    content_texts = [chunk['content'] for chunk in content_chunks]
                    batch_size = 10
                    existing_metadata = None

                    chunk_batches = (
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
                        [
                            content_texts[i : i + batch_size]
                            for i in range(0, len(content_texts), batch_size)
                        ]
                    )
                    print(f"Total chunk batches: {len(chunk_batches)}")

                    for batch_idx, batch in enumerate(chunk_batches):
                        if not any(batch):
                            continue

                        # Run the async function in a new event loop
                        metadata = asyncio.run(process_batch(batch, existing_metadata, input_prompt))
                        
                        if metadata:
                            existing_metadata = metadata.model_dump()
                            print(f"Length of metadata: {len(metadata.data)}")
                    
                    print(f"Document ID {document_id} processed!")

                    # one doc run complete at this point
                    if existing_metadata:                        
                        # update document status as completed
                        self.sql_db.updateCedarDocumentStatus(document_id, {"metadata_status": "completed"})
                    else:
                        # update document status as failed 
                        self.sql_db.updateCedarDocumentStatus(document_id, {"metadata_status": "failed", "last_error": "No metadata extracted."}) 
                        continue
                    
                    # save metadata fields to document metadata table
                    for parent_entity, entity_data in metadata.data.items(): # type: ignore
                        print(f"Parent entity: {parent_entity}")
                        
                        doc_metadata_row = {
                            "document_id": document_id,
                            "run_id": curr_run_id, 
                            "field_name": parent_entity,
                            "field_value": entity_data,
                            "confidence_score": 90,
                            "extraction_method": "gpt-4o",
                        }
                        self.sql_db.insertCedarDocumentMetadata(doc_metadata_row)
                    print(f"Document ID {document_id}: metadata saved!")
                    
                except Exception as e:
                    print("Error in doc level metadata extraction: ", e)
                    self.sql_db.updateCedarDocumentStatus(document_id, {"metadata_status": "failed", "last_error": str(e)}) 
                    continue

            return {"run_id": curr_run_id}
        except Exception as e:
            print("Error: ", str(e))
            return {"error": str(e)}
        
    def download_metadata_csv(self, run_ids: List[int]) -> List[str]:
        """
        This function downloads the metadata from the database and saves it as a CSV file.
        """
        try:
            # fetch all processed docs
            limit = 100
            offset = 0
            runs_ids_str = ",".join(map(str, run_ids))
            print(f"Run IDs: {runs_ids_str}")
            metadata = []
            while True: 
                data = self.sql_db.getRunData(runs_ids_str, limit, offset).data
                if not data:
                    break
                metadata.extend(data)
                print(f"Metadata: {len(metadata)}")
                offset += limit
            
            final_metadata = []
            for run_id in run_ids:
                metadata = self.sql_db.getCedarDocumentMetadata(doc_id).data
                if not metadata:
                    continue

                for row in metadata:
                    final_metadata.append({ 
                        "file_name": doc['readable_filename'],              
                        "document_id": row['id'],
                        "field_name": row['field_name'],
                        "field_value": json.dumps(row['field_value']),
                    })
                    
                
            print(f"Metadata: {len(final_metadata)}")
            # Save metadata as CSV
            if final_metadata:
                import pandas as pd
                df = pd.DataFrame(final_metadata)
                csv_file = "metadata.csv"
                file_path = os.path.join(os.getcwd(), csv_file)
                print(f"File path: {file_path}")
                df.to_csv(file_path, index=False, encoding='utf-8')
                return [file_path, csv_file, os.getcwd()]

            
            
            return None
        except Exception as e:
            print("Error: ", e)
            return None