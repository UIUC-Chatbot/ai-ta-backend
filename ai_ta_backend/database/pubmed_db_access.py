import sqlite3
from contextlib import closing

from flask import Flask, jsonify, request

app = Flask(__name__)

# Database configuration
DATABASE = 'v2-articles.db'


def get_db():
  """Get database connection"""
  db = sqlite3.connect(DATABASE)
  db.row_factory = sqlite3.Row
  return db


@app.route('/getTextFromContextIDBulk', methods=['POST'])
def get_data_bulk():
  """API endpoint to fetch data from SQLite DB for multiple IDs
    Example input: 
    {
        "ids": ["---1PHuidFHAtTDU6WFIB", "p9JJ0YNq-ZqocIypkK__a"]
    }
    """
  try:
    # Get list of IDs from request JSON
    ids = request.get_json().get('ids', [])
    if not ids:
      return jsonify({'error': 'No IDs provided'}), 400

    with closing(get_db()) as db:
      cursor = db.cursor()
      print(f"Searching for {len(ids)} IDs")
      db.execute("PRAGMA busy_timeout = 5000")  # Set 5 second timeout

      # Single query to get both text content and article title
      placeholders = ','.join('?' * len(ids))
      query = f'''
                SELECT c.ID, c.text, a.Title, a.Minio_Path
                FROM contexts c
                LEFT JOIN sections s ON c.Section_ID = s.ID
                LEFT JOIN articles a ON s.Article_ID = a.ID
                WHERE c.ID IN ({placeholders})
            '''
      cursor.execute(query, ids)
      results = cursor.fetchall()

      if not results:
        print("No results found for any ID")
        return jsonify({'error': 'No records found'}), 404

      # Create response dictionary with both text and title
      response = {
          str(row['ID']): {
              'page_content': row['text'],
              'readable_filename': row['Title'] if row['Title'] else 'Unknown Title, sorry!',
              'minio_path': row['Minio_Path']
          } for row in results
      }

      # Report any IDs that weren't found
      missing_ids = set(map(str, ids)) - set(response.keys())
      if missing_ids:
        print(f"IDs not found: {missing_ids}")

      return jsonify(response)

  except Exception as e:
    return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
  app.run(debug=True, port=5001, host='0.0.0.0')
