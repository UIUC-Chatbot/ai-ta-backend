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
    
    # def process_documents(self, input_prompt: str) -> List[Dict[str, Any]]:
    #     """
    #     This function generates metadata from the text chunks and table JSONs extracted from the PDFs.
    #     """
    #     print("Input prompt: ", input_prompt)
    #     try:
    #         # code
    #         # fetch documents with chunk_status = completed and metadata_status = pending/failed
    #         chunks = self.sql_db.getCedarChunks().data

    #         # Group chunks by document_id
    #         from itertools import groupby
    #         from operator import itemgetter

    #         # Sort chunks by document_id to prepare for grouping
    #         sorted_chunks = sorted(chunks, key=itemgetter('document_id'))

    #         # Process each document's chunks
    #         for document_id, doc_chunks in groupby(sorted_chunks, key=itemgetter('document_id')):
    #             doc_chunks = list(doc_chunks)  # Convert iterator to list
    #             print(f"Processing document ID: {document_id}")
                
    #             # Separate table and content chunks
    #             table_chunks = [chunk for chunk in doc_chunks if chunk['chunk_type'] in ['Table', 'TableChunk']]
    #             content_chunks = [chunk for chunk in doc_chunks if chunk['chunk_type'] not in ['Table', 'TableChunk']]

    #             print(f"Table chunks: {len(table_chunks)}")
    #             print(f"Content chunks: {len(content_chunks)}")

    #             # Process content chunks in batches
    #             content_texts = [chunk['content'] for chunk in content_chunks]
    #             batch_size = 10
    #             existing_metadata = None

    #             # Create combined batch processing
    #             chunk_batches = (
    #                 # Process each table chunk individually
    #                 [
    #                     [
    #                         (
    #                             json.dumps(chunk['table_data'])
    #                             if chunk['table_data']
    #                             else chunk['table_html']
    #                         )
    #                     ]
    #                     for chunk in table_chunks
    #                 ]
    #                 +
    #                 # Process content chunks in batches
    #                 [
    #                     content_texts[i : i + batch_size]
    #                     for i in range(0, len(content_texts), batch_size)
    #                 ]
    #             )
    #             print(f"Total chunk batches: {len(chunk_batches)}")

    #             for batch_idx, batch in enumerate(chunk_batches):
    #                 if not any(batch):  # Skip empty batches
    #                     continue

    #                 prompt = """You are an expert at analyzing documents and extracting structured metadata into clean, hierarchical formats.
    #                     Your task is to extract and organize all information into a nested structure that preserves relationships and values. 
    #                     Carefully structure the output to best respond to the user's request. 
    #                     Since information will be shared iteratively and your responses will be saved in existing metadata, feel free to restructure the output so that it is most useful to the user. 
    #                     This might be the case especially when there's lower level information that is not shared yet.

    #                     Output Format:
    #                     {
    #                         "data": {
    #                             "<parent_entity>": {            # Primary/top-level entity identifier
    #                                 "<category>": {             # Logical grouping of related information
    #                                     "<attribute>": <value>   # Attribute-value pairs, can be nested further
    #                                 }
    #                             }
    #                         }
    #                     }

    #                     Important Instructions:
    #                     1. PARENT ENTITY IDENTIFICATION
    #                       - Identify the main top-level entities that serve as primary identifiers
    #                       - These group related information together at the highest level

    #                     2. CATEGORY IDENTIFICATION
    #                       - Identify distinct logical groups of information
    #                       - Each category should group related attributes together

    #                     3. VALUE MAPPING
    #                       - For each parent entity and category:
    #                         * Map every attribute to its exact value
    #                         * Keep text exactly as shown
    #                         * Preserve all formatting and units
    #                         * Maintain relationships between values

    #                     4. DATA QUALITY
    #                       - Preserve exact text and values
    #                       - Don't modify or summarize values
    #                       - Maintain all relationships and hierarchies
    #                       - Don't skip any information

    #                     Remember:
    #                     - Focus on preserving relationships and hierarchies
    #                     - Be thorough in extracting all relevant data
    #                     - Keep the structure consistent across all entries
    #                     - Allow for flexible nesting where needed

    #                     Critical Requirements:
    #                     - Preserve exact text and values
    #                     - Include all fields and values
    #                     - Maintain hierarchical relationships
    #                     - Keep formatting and units intact
    #                     - Don't skip any information
    #                     - Don't summarize or modify values
    #                     - Preserve all specifications, details, attributes, and relationships
    #                     - Do not make up any information, only extract what is present in the document or the existing metadata
    #                     """
                    
    #                 try:
    #                     result = self.extractor.ainvoke(
    #                             {
    #                                 "messages": [
    #                                     {"role": "system", "content": prompt},
    #                                     {
    #                                         "role": "user",
    #                                         "content": "Extract structured tractor metadata with all models at the top level, and their components and attributes and their relationships in a nested structure:\n\n"
    #                                         + "\n\n Document Chunks: ".join(batch),
    #                                     },
    #                                 ],
    #                                 "existing": (
    #                                     {"DocumentMetadata": existing_metadata}
    #                                     if existing_metadata
    #                                     else None
    #                                 ),
    #                             }
    #                     )
    #                     if result and "responses" in result and result["responses"]:
    #                         metadata = DocumentMetadata(
    #                             **result["responses"][0].model_dump()
    #                         )
    #                         existing_metadata = metadata.model_dump()
                        


    #                 except Exception as e:
    #                     print("Error: ", e)
    #                     # self.logger.error(f"Error processing documents: {e}")
    #                     continue

    #             print(f"Length of metadata: {len(metadata.data)}")
    #             for parent_entity, entity_data in metadata.data.items():
    #                 print(f"Parent entity: {parent_entity}")
    #                 print(f"Entity data: {entity_data}")
    #                 break


    #             break
                
    #         return []
    #     except Exception as e:
    #         print("Error: ", e)
    #         # self.logger.error(f"Error processing documents: {e}")
    #         return []

    def process_documents(self, input_prompt: str) -> List[Dict[str, Any]]:
        """
        This function generates metadata from the text chunks and table JSONs extracted from the PDFs.
        """
        print("Input prompt: ", input_prompt)
        try:
            chunks = self.sql_db.getCedarChunks().data
            sorted_chunks = sorted(chunks, key=itemgetter('document_id'))

            async def process_batch(batch, existing_metadata):
                prompt = """You are an expert at analyzing documents and extracting structured metadata into clean, hierarchical formats.
                    Your task is to extract and organize all information into a nested structure that preserves relationships and values. 
                    Carefully structure the output to best respond to the user's request. 
                    Since information will be shared iteratively and your responses will be saved in existing metadata, feel free to restructure the output so that it is most useful to the user. 
                    This might be the case especially when there's lower level information that is not shared yet.

                    Output Format:
                        {
                            "data": {
                                "<parent_entity>": {            # Primary/top-level entity identifier
                                    "<category>": {             # Logical grouping of related information
                                        "<attribute>": <value>   # Attribute-value pairs, can be nested further
                                    }
                                }
                            }
                        }

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
                    """
                try:
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
                        print(f"Result: {result}")
                        metadata = DocumentMetadata(**result["responses"][0].model_dump())
                        return metadata
                except Exception as e:
                    print("Error processing batch:", e)
                    return None

            # Process each document's chunks
            result = []
            for document_id, doc_chunks in groupby(sorted_chunks, key=itemgetter('document_id')):
                try:
                    doc_chunks = list(doc_chunks)
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
                        metadata = asyncio.run(process_batch(batch, existing_metadata))
                        
                        if metadata:
                            existing_metadata = metadata.model_dump()
                            print(f"Length of metadata: {len(metadata.data)}")
                    print("Batch processing complete!")

                    for parent_entity, entity_data in metadata.data.items(): # type: ignore
                        print(f"Parent entity: {parent_entity}")
                        
                        # add entries to cedar_document_metadata table
                        doc_metadata_row = {
                            "document_id": document_id,
                            "field_name": parent_entity,
                            "field_value": entity_data,
                            "confidence_score": 90,
                            "extraction_method": "gpt-4o",
                        }
                        self.sql_db.insertCedarDocumentMetadata(doc_metadata_row)
                    print("Document metadata saved!")
                    # one doc run complete at this point
                    # need to save the metadata to runs table and update the status in document table
                    
                    if existing_metadata:
                        cedar_run_row = {
                            "document_id": document_id,
                            "metadata": existing_metadata,
                        }
                        self.sql_db.insertCedarRun(cedar_run_row)
                        print("Run saved!")
                        
                        # update document status as completed
                        self.sql_db.updateCedarDocumentStatus(document_id, {"metadata_status": "completed"})
                    else:
                        # update document status as failed 
                        self.sql_db.updateCedarDocumentStatus(document_id, {"metadata_status": "failed", "last_error": "No metadata extracted."}) 
                        result.append({"document_id": document_id, "error": "No metadata extracted."})
                    
                except Exception as e:
                    print("Error: ", e)
                    result.append({"document_id": document_id, "error": str(e)})
                    continue

            return result
        except Exception as e:
            print("Error: ", e)
            return []