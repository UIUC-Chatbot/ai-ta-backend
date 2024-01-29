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

**For debugging**, to run an individual file, use this syntax to maintain proper imports and .env vars: `python -m ai_ta_backend.agents.vectordb`

## Project Management // TODOs

**All dev tracked here: https://github.com/orgs/UIUC-Chatbot/projects/5**

## Accounts // services

As a dev, request to be added here:

- [LangSmith org](https://smith.langchain.com/o/f7abb6a0-31f6-400c-8bc1-62ade4b67dc1)
- Sentry.io and PostHog for python errors and logs, respectively.
- [Github Org](https://github.com/UIUC-Chatbot)

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

- Make an embedding for every FUNCTION in the repo.

### Tools for Github agent

- Get a list of all docstrings in the repo (w/ and w/out function signatures)

### Planner

- Plan re-prioritization. Especially when listening to new comments coming in from the user.

# Memory System

Workflow:

1. Ingest content via [Langchain Callbacks](https://python.langchain.com/docs/modules/callbacks/custom_callbacks) to populate our Memory object.
2. Store memory object in a persistent DB (probably Supabase Postgres SQL)
3. On every LLM call, do a DB fetch and construct a prompt in [`create_prompt()` method](langchain/agents/structured_chat/base.py).

Maybe use this library to extract structured data from the callback functions: https://www.askmarvin.ai/components/ai_model/. See the `Auto-output-parsing` section below.

### Prompt template for memory system

- `{some_variable}` represents variables we'll inject
- `<some comment>` represents comments for us to use, not to be part of the final prompt.

## Actual prompt template [(on langsmith hub)](https://smith.langchain.com/hub/my-prompts?organizationId=f7abb6a0-31f6-400c-8bc1-62ade4b67dc1)

```text
## Core memory
### Latest assignment
{Github issue string}

Plan:
{plan}

## Agent action steps, AKA tool use history. (In chronological order, 1 is oldest)
{tool_use_array}

## Messages from human
{human_qa_pairs_array}
```

## Example prompts

```text
## Core memory
### Latest assignment
{Github issue string}

Plan: <Grab directly from starting planning chain. Somehow include which planning steps are done or in progress?>

1. [Done] Get overview of files
2. [Done] Create new branch
3. [In progress now] Update files...
4. Open a pull request with results.

## Agent action steps, AKA tool use history. (In chronological order, 1 is oldest)
1. <EXAMPLE> tool='Calculator' tool_input='2^0.235' tool_output: '1.1769067372187674'
2. <Another tool use...>

## Messages from human
<Store all QA pairs from tool `human`?>
```

### Example full memory prompt

```
## Core memory
### Latest assignment
Title: Create a full command line executable workflow for RNA-Seq on PBMC Samples. Open a new pull request (on a separate branch) and comment the PR number here when you're done.
Opened by user: rohan-uiuc

Body: Experiment Type:
RNA-Seq
Sequencing of total cellular RNA

Workflow Management:
Bash/SLURM
Scripting and job scheduling

Software Stack:
FastQC
MultiQC
STAR
RSEM
samtools
DESeq2

What else to know about the pipeline?
I am working PBMC samples collected from patients that are undergoing immunotherapy.

Use the data files existing in [Report_WholeBrain](https://github.com/KastanDay/ML4Bio/tree/main/Report_WholeBrain) as input for this workflow.

You should write a series of bash scripts and R scripts that can accomplish this task. Open a PR with those scripts when you're done.

## Plan:
1. Read the relevant files in the repository using the `read_file` function.
2. Create a new branch for the changes.
3. Write a series of bash scripts and R scripts to create a command line executable workflow for RNA-Seq on PBMC Samples. The software stack will include FastQC, MultiQC, STAR, RSEM, samtools, and DESeq2.
4. Commit the changes and push them to the new branch.
5. Open a pull request with a clear and concise title and description.
6. Comment on the original issue with the pull request number.
7. Request a review from the user who opened the issue.

## Tool use history (chronological order, 1 is oldest)
1. tool='Calculator' tool_input='2^0.235' log=' I need to use a calculator to solve this. Action Input: 2^0.235'
2. Another tool use...

## Conversation history


## Messages history with your boss
AI: Could you please specify the file you want to read?
Boss: The files in directory data/report
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
