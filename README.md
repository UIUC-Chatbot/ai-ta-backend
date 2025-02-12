# AI TA Backend for UIUC's Course Assistant Chatbot

A Flask application hosting endpoints for AI TA backend.

### 👉 See the main app for details: https://github.com/UIUC-Chatbot/ai-teaching-assistant-uiuc

## License

This project is available under [our Research Use Only license fully defined here](https://github.com/UIUC-Chatbot/self-hostable-ai-ta-backend/blob/main/ResearchUseONLYLicense-UIUC.CHAT.pdf). This license is similar in spirit to the [CC BY-NC 4.0 License](https://creativecommons.org/licenses/by-nc/4.0/) which restricts commercial use.

It's free to use for non-commercial use, like research. Any and all commercial use requires a commercial license, see below.

[![CC BY-NC 4.0 License Image](https://github.com/user-attachments/assets/21f4d62f-6a34-4e73-aae3-3129f81b8140)](https://creativecommons.org/licenses/by-nc/4.0/)


### Commercial Use

For commercial use of this project, you must obtain a separate commercial license. Please contact [otm@illinois.edu](mailto:otm@illinois.edu) and [ai@ncsa.illinois.edu](mailto:ai@ncsa.illinois.edu) to inquire about commercial licensing terms.

Failure to obtain a commercial license for commercial use is a violation of the terms of this project.

## Self host with Docker

### 🎉 Get started with a single command

```bash
sudo bash init.sh
```
This will: 
* Create a `.env` file. You can customize this later to change the default passwords.
* Initialize all our databases (Redis, Minio, Qdrant, Postgres/Suapabse)
* Start the backend service running on http://localhost:3012 To customize HTTP port used as the main entrypoint, set the `FLASK_PORT` variabel in your `.env`.

### Configuring Postgres (Supabase)

It's strongly recommende to change your passwords away from the defaults. The Supabase .env file is separate from the rest of the code for seamless compatibility with Supabase's self hosted offering on github, and to maintain compatibility with their guides and general community information.
The .env file is stored in the local path: `./supabase/docker/.env`

### Configuring Database passwords

Customize your env variables. The SQL database can be any of SQLite, Postgres, and Supabase. The object storage can be Minio or AWS S3. 



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
