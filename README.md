# AI TA Backend for UIUC's Course Assistant Chatbot

A Flask application hosting endpoints for AI TA backend.

### 👉 See the main app for details: https://github.com/UIUC-Chatbot/ai-teaching-assistant-uiuc

## License

This project is available under the [CC BY-NC 4.0 License](https://creativecommons.org/licenses/by-nc/4.0/) which restricts commercial use.

[![CC BY-NC 4.0 License Image](https://github.com/user-attachments/assets/21f4d62f-6a34-4e73-aae3-3129f81b8140)](https://creativecommons.org/licenses/by-nc/4.0/)


### Commercial Use

For commercial use of this project, you must obtain a separate commercial license. Please contact [kvday2@illinois.edu](mailto:kvday2@illinois.edu) and [kindrtnk@illinois.edu](mailto:kindrtnk@illinois.edu) to inquire about commercial licensing terms.

Failure to obtain a commercial license for commercial use is a violation of the terms of this project.

## Docker Deployment

### Supabase

1. Duplicate `.env.example` from `supabase/docker/.env.example` and rename it to `.env`. (example: cp ./supabase/docker/.env.example ./supabase/docker/.env)
2. Customize your env variables as needed in the supabase docker

### Self-host docker

1. Duplicate `.env.template` and rename it to `.env`. E.g. `cp .env.template .env`
2. Customize your env variables. Your vector database can be either Qdrant and Pinecone. The SQL database can be any of SQLite, Postgres, and Supabase. The object storage can be Minio or AWS S3. 

### Running simultaneously

We've created an `init.sh` file to run both docker-compose files with run command. To do this, first initialize the `init.sh` with right permission.

```bash
chmod +x init.sh
./init.sh #runs the script
```

To customize HTTP port used as the main entrypoint, set the `FLASK_PORT` variabel in your `.env`. It defaults to 8188.

Works on version: `Docker Compose version v2.27.1-desktop.1`

Works on Apple Silicon M1 `aarch64`, and `x86`.


### 🛠️ Technical Architecture

![Architecture diagram](https://github.com/UIUC-Chatbot/ai-ta-backend/assets/13607221/bda7b4d6-79ce-4d12-bf8f-cff9207c37af)

## Documentation

See docs on https://docs.uiuc.chat

## 📣 Development

If you're interested in contributing, check out our [official developer quickstart](https://docs.uiuc.chat/developers/developer-quickstart).

For local dev: 

1. Rename `.env.template` to `.env` and fill in the required variables
2. Install Python requirements `pip install -r requirements.txt`
3. Start the server for development (with live reloads) `cd ai_ta_backend` then `flask --app ai_ta_backend.main:app --debug run --port 8188`


### Course metadata structure

```text
'text': doc.page_content,
'readable_filename': doc.metadata['readable_filename'],
'course_name ': doc.metadata['course_name'],
's3_path': doc.metadata['s3_path'],
'pagenumber': doc.metadata['pagenumber_or_timestamp'], # this is the recent breaking change!!
# OPTIONAL properties
'url': doc.metadata.get('url'), # wouldn't this error out?
'base_url': doc.metadata.get('base_url'),
```


### Note

For Supabase, the current version we are using is v1.24.09 ([link](https://github.com/supabase/supabase/tree/v1.24.09))