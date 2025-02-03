import requests

def test_warm_ai():
    url = "http://localhost:8000/api/chat-api/warm-ai"
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        "query": "Show me all users who signed up last week"
    }

    response = requests.post(url, headers=headers, json=data)
    print("Status Code:", response.status_code)
    print("Response:", response.json())

if __name__ == "__main__":
    test_warm_ai()