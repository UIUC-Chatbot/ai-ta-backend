# migrating re-scraped cropwizard data from SQL to Qdrant

import os
import sys
import uuid
import logging
from typing import List, Dict, Any
from datetime import datetime
import time
from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path to import from ai_ta_backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.sql import SQLDatabase
from qdrant_client import QdrantClient, models
from qdrant_client.models import PointStruct

# Initialize Qdrant client
cropwizard_client = QdrantClient(url=os.environ['CROPWIZARD_QDRANT_URL'],
                                 port=443,
                                 https=True,
                                 api_key=os.environ['QDRANT_API_KEY'])

# Initialize SQL database client
sql_db = SQLDatabase()

def get_cropwizard_documents_batch(offset: int = 0, limit: int = 10) -> List[Dict[Any, Any]]:
    """
    Query documents from the SQL database where course_name = 'cropwizard-1.5' in batches
    
    Args:
        offset (int): Number of records to skip
        limit (int): Maximum number of records to return
    
    Returns:
        List[Dict[Any, Any]]: List of document records from the database
    """
    try:
        # Query the documents table for cropwizard-1.5 course with pagination
        response = sql_db.supabase_client.table(
            os.environ['SUPABASE_DOCUMENTS_TABLE']
        ).select('*').eq('course_name', 'cropwizard-1.5').gte('created_at', '2025-01-01').range(offset, offset + limit - 1).execute()
        
        # Extract data from response
        documents = response.data
        for document in documents:
            print(document['url'])
        
        print(f"Retrieved {len(documents)} documents for cropwizard-1.5 (offset: {offset}, limit: {limit})")
        return documents
    except Exception as e:
        print(f"Error retrieving cropwizard documents: {str(e)}")
        return []

def upsert_to_qdrant(documents: List[Dict[Any, Any]]) -> bool:
    """
    Upsert documents to Qdrant
    
    Args:
        documents (List[Dict[Any, Any]]): List of document records from the database
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not documents:
        print("No documents to upsert")
        return False
    
    try:
        vectors = []
        vector_ids = []
        
        for document in documents:
            # Process each document's contexts
            if 'contexts' not in document or not document['contexts']:
                print(f"Document {document.get('url')} has no contexts, skipping")
                continue
                
            for context in document['contexts']:
                # Create a unique ID for each vector
                vector_id = str(uuid.uuid4())
                vector_ids.append(vector_id)
                
                # Extract the embedding from the context
                embedding = context.get('embedding')
                if not embedding:
                    print(f"Context in document {document.get('id')} has no embedding, skipping")
                    continue
                
                # Create metadata payload similar to ingest.py
                payload = {
                    "course_name": document.get('course_name'),
                    "s3_path": document.get('s3_path'),
                    "readable_filename": document.get('readable_filename'),
                    "url": document.get('url'),
                    "base_url": document.get('base_url'),
                    "page_content": context.get('text'),
                    "pagenumber": context.get('pagenumber'),
                    "timestamp": context.get('timestamp'),
                    "chunk_index": context.get('chunk_index'),
                    "migrated_at": datetime.now().isoformat()
                }

                #print("payload: ", payload)
                
                # Add to vectors list
                vectors.append(
                    PointStruct(id=vector_id, vector=embedding, payload=payload)
                )
        
        if vectors:
            print(f"Upserting {len(vectors)} vectors to cropwizard collection...")
            # Use individual points instead of Batch
            cropwizard_client.upsert(
                collection_name='cropwizard',
                points=vectors,
            )
            print("Upsert successful")
            return True
        else:
            print("No vectors to upsert")
            return False
            
    except Exception as e:
        logging.error("Error in QDRANT upload: ", exc_info=True)
        err = f"Error in QDRANT upload: {e}"
        if "timed out" in str(e):
            # timed out error is fine, task will continue in background
            print("Qdrant upload timed out, but will continue in background")
            return True
        else:
            print(err)
            return False

def migrate_cropwizard_data(batch_size: int = 10):
    """
    Migrate cropwizard data from SQL to Qdrant in batches
    
    Args:
        batch_size (int): Number of records to process in each batch
    """
    offset = 60000
    total_processed = 60000
    
    while True:
        # Get batch of documents
        documents = get_cropwizard_documents_batch(offset, batch_size)
        
        # If no more documents, break
        if not documents:
            break
            
        # Upsert to Qdrant
        success = upsert_to_qdrant(documents)
        
        # Update counters
        total_processed += len(documents)
        offset += batch_size
        print("current offset: ", offset)
        print(f"Processed {total_processed} documents so far")
        time.sleep(5)
        
        # If batch is smaller than batch_size, we've reached the end
        if len(documents) < batch_size:
            break
    
    print(f"Migration complete. Total documents processed: {total_processed}")

# Example usage
if __name__ == "__main__":
    migrate_cropwizard_data(batch_size=100)
    