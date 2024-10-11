import sqlite3
from uuid import uuid4
from qdrant_client import QdrantClient, models
import json

from sentence_transformers import SentenceTransformer
encoder = SentenceTransformer("all-MiniLM-L6-v2")

db_path = '/home/guest/ai-ta-backend/UIUC_Chat/pdf-parsing/v2-articles.db'
client = QdrantClient(url="https://dankchat.humpback-symmetric.ts.net", port=443, https=True, api_key="o3d2Ty8RosrR9uSnhu488UVsywDNYr4H23tW")



def create_qdrant(client):
    # try:
    #     client.delete_collection(collection_name="embedding")
    #     print("Collection 'embedding' deleted successfully.")
    # except Exception as e:
    #     print(f"Error deleting collection: {e}")

    try:
        collection_info = client.get_collection(collection_name="embedding")
        print("Collection 'embedding' already exists.")
    except Exception as e:
        print("Collection does not exist, creating a new one.")
        client.create_collection(
            collection_name="embedding",
            vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
        )

def store_embeddings_in_qdrant(client, db_path):
    sql_connection = sqlite3.connect(db_path)
    cursor = sql_connection.cursor()
    cursor.execute("""
        SELECT a.id, s.id, a.authors, c.`Embedding_nomic_1.5`, c.id
        FROM articles AS a
        JOIN sections AS s ON a.id = s.article_id
        JOIN contexts AS c ON s.id = c.section_id
    """)

    rows = cursor.fetchall()

    points = []
    for row in rows:
        embedding = json.loads(row[3]) if isinstance(row[3], str) else row[3]

        points.append(
            models.PointStruct(
                id=str(uuid4()),
                payload={
                    "article_id": row[0],
                    "section_id": row[1],
                    "authors": row[2],
                    "context_id": row[4],
                },
                vector=embedding,
            )
        )

    client.upsert(
        collection_name="embedding",
        points=points,
    )

    sql_connection.close()

# store_embeddings_in_qdrant()

# collection_info = client.get_collection(collection_name="embedding")

# print(collection_info)

# hits = client.search(
#     collection_name="embedding",
#     query_vector=[0.1] * 768,
#     # query_filter=models.Filter(
#     #     must=[models.FieldCondition(key="authors", match=models.MatchValue(value="Oliver"))],
#     # ),
#     limit=1,
# )

# for hit in hits:
#     print(hit.id, hit.payload, hit.score)