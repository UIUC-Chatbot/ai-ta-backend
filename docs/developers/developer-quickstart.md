---
description: Thanks for contributing to UIUC.chat ❤️
---

# Developer Quickstart

## Start here

* [ ] Send me (kvday2@illinois.edu) an email and request to be added to:
  * GitHub Organization, <mark style="color:yellow;">include your GitHub username</mark>.
  * Secrets manager, <mark style="color:yellow;">include your preferred email address</mark>.
  * Supabase dashboard, <mark style="color:yellow;">include your GitHub's email address</mark>.

👉 Skip to [Frontend](developer-quickstart.md#frontend-setup) or [Backend](developer-quickstart.md#backend-setup) setup instructions.

### Key accounts

* Google: `caiincsa@gmail.com`
* Managed services: Vercel, Railway, Beam, Supabase, S3, Posthog, Sentry.
* Self-hosted: Qdrant, Ollama.
* Task management via [our Github Projects board](https://github.com/orgs/UIUC-Chatbot/projects/2).

## Set up Infiscal

{% hint style="warning" %}
You must setup an account before continuing, for our secrets service [Infisical](https://infisical.com/docs/documentation/getting-started/introduction).\
Confirm you can login here: [https://env.ncsa.ai/](https://env.ncsa.ai/)
{% endhint %}

Instead of sharing .env files manually, we use Infiscal as a central password manager for devs. We use its CLI and web interface.

See the [CLI install docs](https://infisical.com/docs/cli/overview) for Linux/Windows instructions. Or the [CLI usage docs](https://infisical.com/docs/cli/usage).

{% tabs %}
{% tab title="brew" %}
```bash
# install
brew install infisical/get-cli/infisical
```
{% endtab %}

{% tab title="apt-get" %}
```bash
# add the repository
curl -1sLf \
'https://dl.cloudsmith.io/public/infisical/infisical-cli/setup.deb.sh' \
| sudo -E bash

# install
sudo apt-get update && sudo apt-get install -y infisical
```
{% endtab %}
{% endtabs %}

## Frontend Setup

Frontend repo: [https://github.com/CAII-NCSA/uiuc-chat-frontend](https://github.com/CAII-NCSA/uiuc-chat-frontend)

```bash
# clone the repo somewhere good
git clone git@github.com:CAII-NCSA/uiuc-chat-frontend.git
```

### (1/2) Install dev dependencies

{% hint style="warning" %}
follow these instructions _**in order;**_ it's tested to work brilliantly.&#x20;
{% endhint %}

Use Node version `18.xx` LTS

```bash
# check that nvm is installed (any version). 
# easily install here: https://github.com/nvm-sh/nvm?tab=readme-ov-file#installing-and-updating
nvm --version 

# use node version 18
nvm install 18
nvm use 18
node --version  # v18.20.4
```

Install dev dependencies

```bash
# navigate to the root of the github
cd path/to/ai-ta-frontend

# install all necessary dependencies 
npm i 
```

### (2/2) Set up secrets

```bash
# navigate to the root of the github
cd path/to/ai-ta-frontend

infisical login
# ⭐️ --> select "Self Hosting"
# ⭐️ --> enter "https://env.ncsa.ai"
# ⭐️ click the login link
# ⭐️ likely enter your main computer password
```

### Last step: start dev server!&#x20;

You will need to run the below command once for the initial setup

```bash
# Use our linter, Trunk SuperLinter. 
# Just run the commande below once to install it.
# Now every `git commit` and `git push` will trigger linting.
# We suggest accepting the auto-formatting suggestions.

npm exec trunk check
```

Run the app on your local machine

<pre class="language-bash"><code class="lang-bash"><strong># run server with secrets &#x26; live reload
</strong># as defined in package.json, this actually runs: infisical run --env=dev -- next dev
npm run dev

# you should see a log of the secrets being injected
INF Injecting 32 Infisical secrets into your application process
...
  ▲ Next.js 13.5.6
  - Local:        http://localhost:3000
  
# cmd + click on the URL to open your browser :) 
</code></pre>

`npm run dev` is the most important command you'll use every dev session.

***

## Backend Setup

Backend repo: [https://github.com/UIUC-Chatbot/ai-ta-backend](https://github.com/UIUC-Chatbot/ai-ta-backend)

```bash
# clone the repo somewhere good
git clone git@github.com:UIUC-Chatbot/ai-ta-backend.git
```

### (1/2) Install dev dependencies

Use a python virtual environment, here I'll use `conda`.

Use <mark style="color:yellow;">python 3.10</mark>.

```bash
conda create --name ai-ta-backend python=3.10 -y

conda activate ai-ta-backend

pip install -r requirements.txt
```

### (2/2) Set up secrets

{% hint style="warning" %}
You must setup an account before continuing, for our secrets service [Infisical](https://infisical.com/docs/documentation/getting-started/introduction).\
Confirm you can login here: [https://env.ncsa.ai/](https://env.ncsa.ai/)

Also make sure to install Infiscal in your local machine as mentioned above
{% endhint %}

<pre><code># navigate to the root of the github
cd path/to/ai-ta-backend
<strong>
</strong><strong>infisical login
</strong># ⭐️ --> select "Self Hosting"
# ⭐️ --> enter "https://env.ncsa.ai"
# ⭐️ click the login link
# ⭐️ likely enter your main computer password
</code></pre>

### Last step: start dev server!

```bash
# start dev server on localhost:8000
infisical run --env=dev -- flask --app ai_ta_backend.main:app --debug run --port 8000
```

Now you can write new endpoints in `ai-ta-backend/main.py` and call them using [Postman](https://www.postman.com/).&#x20;



Thanks! For any questions at all just email me (kvday2@illinois.edu). I'm friendly, promise.
