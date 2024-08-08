---
description: Thanks for contributing to UIUC.chat ❤️
---

# Developer Quickstart

## Start here

* [ ] Send me (kvday2@illinois.edu) an email and request to be added to:
  * GitHub Organization, <mark style="color:yellow;">include your GitHub username</mark>.
  * Secrets manager, <mark style="color:yellow;">include your preferred email address</mark>.

👉 Skip to [Frontend](developer-quickstart.md#frontend-setup) or [Backend](developer-quickstart.md#backend-setup) setup instructions.

### Key accounts

* Google: `caiincsa@gmail.com`
* Managed services: Vercel, Railway, Beam, Supabase, S3.
* Self-hosted: Qdrant, Ollama
* Task management via [our Github Projects board](https://github.com/orgs/UIUC-Chatbot/projects/2)

## Frontend Setup

```bash
# clone the repo somewhere good
git clone git@github.com:KastanDay/ai-ta-frontend.git
```

### (1/2) Set up dev environment&#x20;

Use Node version `18.xx` LTS

```bash
# ensure nvm is installed (any version). Docs: https://github.com/nvm-sh/nvm?tab=readme-ov-file#installing-and-updating
nvm --version 

# use node version 18
nvm install 18
nvm use 18
node --version  # v18.20.2
```

Install dev dependencies

```bash
# navigate to the root of the github
cd path/to/ai-ta-frontend

# install all necessary dependencies 
npm i 
```

Now you _could_ `npm run dev`, but we need the secrets first...

### (2/2) Set up secrets

{% hint style="warning" %}
You must setup an account before continuing, for our secrets service [Infisical](https://infisical.com/docs/documentation/getting-started/introduction).\
Confirm you can login here: [https://env.ncsa.ai/](https://env.ncsa.ai/)
{% endhint %}

Instead of sharing .env files manually, we use Infiscal as a central password manager for devs. We use its CLI and web interface.

See the [CLI install docs](https://infisical.com/docs/cli/overview) for Linux/Windows instructions. Or the [CLI usage docs](https://infisical.com/docs/cli/usage).

```bash
# install
brew install infisical/get-cli/infisical
```

#### Login

```bash
infisical login
# ⭐️ --> select "Self Hosting"
# ⭐️ --> enter "https://env.ncsa.ai"
# ⭐️ Likely enter your main computer password
```

#### Initialize and configure

```bash
# navigate to the root of the github
cd /path/to/ai-ta-frontend

# initialize infisical
infisical init
# ⭐️ --> choose UIUC.chat
# ⭐️ --> choose ai-ta-frontend
```

#### Last step: Start the dev server!&#x20;

```bash
# start dev server (with live reload), using our secrets.
infisical run --env=dev -- npm run dev
# 🧠 infisical just adds env vars, nothing more. Otherwise it's normal `npm run dev`.

# you should see a log of the secrets being injected
INF Injecting 32 Infisical secrets into your application process
  ▲ Next.js 13.5.6
  - Local:        http://localhost:3000
  
# cmd + click on the URL to open your browser :) 
```

That's the most important command you'll use every dev session.

***

## Backend Setup

```bash
# clone the repo somewhere good
git clone git@github.com:UIUC-Chatbot/ai-ta-backend.git
```

### (1/2) Install dev dependencies

Use some python virtual environment, here I'll use `conda`.

Use <mark style="color:yellow;">python 3.10</mark>.

```bash
conda create -n ai-ta-backend python=3.10 -y

conda activate ai-ta-backend

pip install -r requirements.txt
```

### (2/2) Set up secrets

{% hint style="warning" %}
You must setup an account before continuing, for our secrets service [Infisical](https://infisical.com/docs/documentation/getting-started/introduction).\
Confirm you can login here: [https://env.ncsa.ai/](https://env.ncsa.ai/)
{% endhint %}

<details>

<summary>👉 Install Infisical, if you haven't yet</summary>

Instead of sharing .env files manually, we use Infiscal as a central password manager for devs. We use its CLI and web interface.

See the [CLI install docs](https://infisical.com/docs/cli/overview) for Linux/Windows instructions. Or the [CLI usage docs](https://infisical.com/docs/cli/usage).

```bash
# install
brew install infisical/get-cli/infisical
```

#### Login

```bash
infisical login
# ⭐️ --> select "Self Hosting"
# ⭐️ --> enter "https://env.ncsa.ai"
# ⭐️ Likely enter your main computer password
```

</details>

#### Configure secrets for backend

```bash
# navigate to the root of the github
cd path/to/ai-ta-backend

# initialize infisical
infisical init
# ⭐️ --> choose UIUC.chat
# ⭐️ --> choose ai-ta-frontend
```

### Last step: Start dev server!

```bash
# start dev server on localhost:8000
infisical run --env=dev -- flask --app ai_ta_backend.main:app --debug run --port 8000
```

Now you can write new endpoints in `ai-ta-backend/main.py` and call them using [Postman](https://www.postman.com/).&#x20;



Thanks! For any questions at all just email me (kvday2@illinois.edu). I'm friendly, promise.
