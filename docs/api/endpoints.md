---
description: The most important API endpoints developers will want to use.
layout:
  title:
    visible: true
  description:
    visible: true
  tableOfContents:
    visible: true
  outline:
    visible: true
  pagination:
    visible: true
---

# Endpoints

## **`/chat` API Endpoint**

\
The /chat endpoint is designed to handle chat requests, providing both streaming and non-streaming response options. It supports image content and ensures that the chat responses are processed efficiently. Before you can start using the API, you need to [generate an API key](api-keys.md).

#### **Using the API Key**

With your API key in hand, you can now make authenticated requests to the /chat endpoint. Below are examples of how to use the API for different scenarios.

### Streaming Response Example

For a streaming response, where messages are sent and received in real-time, use the following Python code snippet:\


```python
import requests

url = "https://uiuc.chat/api/chat-api/chat"
headers = {
    'Content-Type': 'application/json',
}
data = {
    "model": "gpt-4",
    "messages": [
        {
            "role": "system",
            "content": "Your system prompt here"
        },
        {
            "role": "user",
            "content": "What is in these documents?"
        }
    ],
    "openai_key": "YOUR-OPENAI-KEY-HERE",
    "temperature": 0.1,
    "course_name": "your-course-name",
    "stream": True,
    "api_key": "YOUR_API_KEY"
}

response = requests.post(url, headers=headers, json=data)
print(response.text)
```

### Non-Streaming Response Example

```python
import requests

url = "https://uiuc.chat/api/chat-api/chat"
headers = {
    'Content-Type': 'application/json'
}
data = {
    "model": "gpt-4",
    "messages": [
        {
            "role": "system",
            "content": "Your system prompt here"
        },
        {
            "role": "user",
            "content": "What is in these documents?"
        }
    ],
    "openai_key": "YOUR-OPENAI-KEY-HERE",
    "temperature": 0.1,
    "course_name": "your-course-name",
    "stream": False,
    "api_key": "YOUR_API_KEY"
}

response = requests.post(url, headers=headers, json=data)
print(response.text)
```

### Image Input Example

To send an image as part of the conversation, include the image URL in the messages array:

Note: Image input is only allowed with gpt-4-vision-preview model for now

```python
import requests
import json

url = "https://uiuc.chat/api/chat-api/chat"
headers = {
  'Content-Type': 'application/json'
}
payload = {
  "model": "gpt-4-vision-preview",
  "messages": [
    {
      "role": "system",
      "content": "Your system prompt here"
    },
    {
      "role": "user",
      "content": [
        {
          "type": "image_url",
          "image_url": {
            "url": "you image url here"
          }
        },
        {
          "type": "text",
          "text": "Give me more information on the action depicted in this image."
        }
      ]
    }
  ],
  "openai_key": "YOUR-OPENAI-KEY-HERE",
  "temperature": 0.1,
  "course_name": "your-course-name",
  "stream": False,
  "api_key": "YOUR_API_KEY"
}

response = requests.post(url, headers=headers, json=data)
print(response.text)
```

### Multiple Messages in a Conversation

```python
import requests

url = "https://uiuc.chat/api/chat-api/chat"
headers = {
    'Content-Type': 'application/json',
}
data = {
    "model": "gpt-4",
    "messages": [
        {
          "role": "system",
          "content": "You are a helpful assistant."
        },
        {
          "role": "user",
          "content": "What can you tell me about the history of artificial intelligence?"
        },
        {
          "role": "assistant",
          "content": "Artificial intelligence has a long history dating back to the mid-20th century, with key milestones such as the development of the Turing Test and the creation of early neural networks."
        },
        {
          "role": "user",
          "content": [
            {
              "type": "text",
              "text": "Here is an image related to AI, can you analyze it?"
            },
            {
              "type": "image_url",
              "image_url": {
                "url": "https://example.com/path-to-your-image.png"
              }
            }
          ]
        }
    ],
    "openai_key": "YOUR-OPENAI-KEY-HERE",
    "temperature": 0.1,
    "course_name": "your-course-name",
    "stream": True,
    "api_key": "YOUR_API_KEY"
}

response = requests.post(url, headers=headers, json=data)
print(response.text)
```

#### Coming soon

Document ingest via API. Currently only supported via the website GUI.
