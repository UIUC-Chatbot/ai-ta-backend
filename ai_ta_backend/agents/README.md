## Usage

To start, run this from the top level of git repo:
```bash
conda create -n ai-ta-backend python=3.10 -y
conda activate ai-ta-backend
pip install -r requirements.txt

playwright install # for the AI to brows the web

# Run command
flask --app ai_ta_backend.main:app --debug run --port 8000
```

```bash
# run command w/ logging
newrelic-admin run-program flask --app ai_ta_backend.main:app --debug run --port 8000
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

# Memory System

1. Ingest content via Langchain Callbacks to populate our Memory object.
2. Store memory object in a persistent DB (probably Supabase Postgres SQL)
3. On every LLM call, do a DB fetch and construct a prompt.

Maybe use this library to extract structured data from the callback functions: https://www.askmarvin.ai/components/ai_model/. See the `Auto-output-parsing` section below.

### Prompt template for memory system
* `{some_variable}` represents variables we'll inject
* `<some comment>` represents comments for us to use, not to be part of the final prompt. 

```text
## Core memory 
Overall goal: {original_gaol}
Original task: (full Github Issue)

Plan: (directly from planning chain). Which planning steps are done or in progress? 

1. [Done] Get overview of files
2. [Done] Create new branch
3. [In progress now] Update files...
4. Open a pull request with results.

## Tool use history 
1. <EXAMPLE> tool='Calculator' tool_input='2^0.235' log=' I need to use a calculator to solve this.\nAction: Calculator\nAction Input: 2^0.235'
2. Another tool use... 

## Conversation history (maybe build on ConvoSummaryBuffer? https://python.langchain.com/docs/modules/memory/types/summary_buffer)


## Messages from human
<Store all QA pairs from tool `human`?>
```

### Auto-output-parsing 

Seems to work great. Can add more detail to the parsing of each variable via the "instruction()" param. 

```python
## AUTO PARSING !! 
# https://www.askmarvin.ai/components/ai_model/

from typing import List, Optional
from pydantic import BaseModel
from marvin import ai_model
from dotenv import load_dotenv
load_dotenv(override=True)
import os
import marvin 
marvin.settings.openai.api_key = os.environ['OPENAI_API_KEY']
# @ai_model(model="gpt-35-turbo", temperature=0)
# @ai_model

@ai_model(model="openai/gpt-3.5-turbo", temperature=0)
class PackagesToInstall(BaseModel):
    apt_packages_to_install: Optional[List[str]]
    pip_packages_to_install: Optional[List[str]]
    r_packages_to_install: Optional[List[str]]

PackagesToInstall(input) # Github issue string as input

'''
Result:
PackagesToInstall(
    apt_packages_to_install=['samtools'], 
    pip_packages_to_install=['multiqc', 'star'], 
    r_packages_to_install=['DESeq2', 'rsem']
)
'''
```