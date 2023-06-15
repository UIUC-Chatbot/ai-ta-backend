## AI TA Backend for UIUC's Course Assistant Chatbot
A Flask application hosting endpoints for AI TA backend.

### 👉 See the main app for details: https://github.com/UIUC-Chatbot/ai-teaching-assistant-uiuc

### 🛠️ Technical Architecture
Hosted (mostly for free) on [Railway](https://railway.app/).
Architecture diagram of Flask + Next.js & React hosted on Vercel. 
![Architecture diagram](https://github.com/UIUC-Chatbot/ai-ta-backend/assets/13607221/bda7b4d6-79ce-4d12-bf8f-cff9207c37af)

## Documentation
Automatic [API Reference](https://uiuc-chatbot.github.io/ai-ta-backend/reference/)

## 📣 Development

- Install Python requirements `pip install -r requirements.txt`
- Start the server for development (with live reloads) `cd ai_ta_backend` then `flask --app ai_ta_backend.main:app --debug run --port 8000`

The docs are auto-built and deployed to [our docs website](https://uiuc-chatbot.github.io/ai-ta-backend/) on every push. Or you can build the docs locally when writing:
- `mkdocs serve`
