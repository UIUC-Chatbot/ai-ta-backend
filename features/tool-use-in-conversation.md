---
description: >-
  To best answer your question, the LLM system uses tools as needed. Create your
  own tools with N8N.
---

# Tool use in conversation

## Demo

{% embed url="https://www.youtube.com/watch?v=sSai_F1cbEI" %}



## Get access

Tools are invite-only during beta. Just shoot me an email and I'll send you an onboarding invite no problem. &#x20;

`Email me: kvday2@illinois.edu`

I'm happy to onboard anyone. No need to justify anything, no calls required.&#x20;

### Development

During beta, try using the feature branch here: [https://uiuc-chat-git-n8n-ui-kastandays-projects.vercel.app/](https://uiuc-chat-git-n8n-ui-kastandays-projects.vercel.app/)

1. Define tools in \`uiuc.chat/\<YOUR-PROJECT>/tools
2. Enable the tools you want active in your project
3. Start chatting, tools will be invoked as needed.

<figure><img src="../.gitbook/assets/image (1).png" alt=""><figcaption><p>The concept of "tool use." The LLM parses a user input and determines if any of the available tools are relevant. If so, the AI generates the input params and then our code manually invokes the tool requested by the LLM. Finally, the output is sent back to the LLM to generate a final answer consider the tool output. <a href="https://python.langchain.com/v0.1/docs/use_cases/tool_use/">Image source</a>.</p></figcaption></figure>

