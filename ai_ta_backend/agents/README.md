## Usage

To start, run this from the top level of git repo:
```bash
pip install -r requirements.txt
flask --app ai_ta_backend.main:app --debug run --port 8000
```

**For debugging**, to run an individual file, use this syntax to maintain proper imports and .env vars: `python -m ai_ta_backend.agents.vectordb`

## Project Management // TODOs

**All dev tracked here: https://github.com/orgs/UIUC-Chatbot/projects/5**

## Accounts // services 

As a dev, request to be added here:
* [LangSmith org](https://smith.langchain.com/o/f7abb6a0-31f6-400c-8bc1-62ade4b67dc1)
* [NewRelic logging / observability](https://one.newrelic.com/admin-portal/organizations/users-list?account=4209060&begin=1698180809228&end=1698180929228&state=5be3d246-c297-3140-1cb9-d6cc0aa1af17)
* [Github Org](https://github.com/UIUC-Chatbot)

## Overview (in progress)

1. An Issue or PR is opened on Github. All these entrance points are defined in `github_webhoook_handlers.py`.

2. Our agents respond to the issue/PR and try to implement it.

# Top level agents
1. Plan & Execute agent in `workflow_agent.py`
1. ReAct agent in `github_agent.py`
1. TOT agent tbd: https://api.python.langchain.com/en/latest/experimental_api_reference.html#module-langchain_experimental.tot

## Prompts
Store all prompts in LangSmith Hub: https://smith.langchain.com/hub/kastanday?organizationId=f7abb6a0-31f6-400c-8bc1-62ade4b67dc1


# Cool features to implement

### Tools for search / retrieval

* Make an embedding for every FUNCTION in the repo.

### Tools for Github agent

* Get a list of all docstrings in the repo (w/ and w/out function signatures)

### Planner

* Plan re-prioritization. Especially when listening to new comments coming in from the user.
