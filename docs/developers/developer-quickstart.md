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

## Frontend Setup

```bash
# clone the repo somewhere good
git clone git@github.com:KastanDay/ai-ta-frontend.git
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

# Use our linter, Trunk SuperLinter. Just run it once to install it.
# Now every `git commit` and `git push` will trigger linting.
# I suggest accepting the auto-formatting suggestions.
npm exec trunk check
```

Now you _could_ `npm run dev`, but we need the secrets first...

### (2/2) Set up secrets

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

#### Login

You only have to login once per computer.

```bash
infisical login
# ⭐️ --> select "Self Hosting"
# ⭐️ --> enter "https://env.ncsa.ai"
# ⭐️ click the login link
# ⭐️ likely enter your main computer password
```

### Last step: start dev server!&#x20;

```bash
# run server with secrets & live reload
# as defined in package.json, this actually runs: infisical run --env=dev -- next dev
npm run dev

# you should see a log of the secrets being injected
INF Injecting 32 Infisical secrets into your application process
...
  ▲ Next.js 13.5.6
  - Local:        http://localhost:3000
  
# cmd + click on the URL to open your browser :) 
```

`npm run dev` is the most important command you'll use every dev session.

***

## Backend Setup

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
# ⭐️ click the login link
# ⭐️ likely enter your main computer password
```

</details>

### Last step: start dev server!

```bash
# start dev server on localhost:8000
infisical run --env=dev -- flask --app ai_ta_backend.main:app --debug run --port 8000
```

Now you can write new endpoints in `ai-ta-backend/main.py` and call them using [Postman](https://www.postman.com/).&#x20;



Thanks! For any questions at all just email me (kvday2@illinois.edu). I'm friendly, promise.
