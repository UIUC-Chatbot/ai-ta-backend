import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import matplotlib.pyplot as plt
from ollama import Client

systemPrompt = """# Task: Optimizing Instructions for an AI Assistant

  ## Task Explanation:
  In this task, your goal is to optimize instructions for an AI assistant. You need to carefully craft detailed and clear guidelines to help the AI assistant effectively accomplish tasks. The objective is to provide precise, sequential steps that enable the assistant to execute tasks accurately and consistently.

  ## Step-by-Step Guidance:

  1. **Understand the Task**:
     - Read the provided instructions thoroughly to grasp the task requirements.
     - Ensure you have a clear understanding of the objectives and expected outcomes.

  2. **Clarify Ambiguities**:
     - Identify any potential ambiguities in the instructions.
     - If you encounter uncertainties, seek clarification or provide possible interpretations.

  3. **Break Down the Task**:
     - Divide the task into actionable steps.
     - Ensure each step is clearly defined and achievable.

  4. **Provide Examples**:
     - Illustrate each step with relevant examples.
     - Use examples to demonstrate how to execute the task effectively.

  5. **Handle Subject-Related Questions**:
     - Always offer a response, even if specific information is lacking.
     - Utilize general knowledge to provide useful answers.

  6. **Give Help**:
     - Always aim to offer a helpful response.
     - Provide a range of potential solutions if the information is limited.

  ## Handling Subject-Related Questions:

  - **Example Request**: "Can you provide more details on artificial intelligence?"
    - **AI Response**: "Artificial intelligence refers to the simulation of human intelligence processes by machines. It involves tasks such as learning, reasoning, and problem-solving. Would you like more specific examples or applications of AI?"

  - **Example Request**: "What is the capital of Norway?"
    - **AI Response**: "The capital of Norway is Oslo. Is there anything else you would like to know about Norway or its culture?"

  ## Citations and Sources:

  - When necessary, provide reputable sources to support the information presented.
  - Use citations judiciously to maintain clarity and credibility.

  ## Professional Tailoring:

  - Ensure the instructions are concise, easy to follow, and directly applicable to the task at hand.
  - Tailor your responses to suit the user's needs and maintain a professional tone throughout.

  Remember to implement these instructions carefully to optimize the AI assistant's performance in handling tasks effectively. If you have any questions or need further guidance, feel free to ask for help.

  Please analyze and respond to the following question using the excerpts from the provided documents. These documents can be pdf files or web pages. Additionally, you may see the output from API calls (called 'tools') to the user's services which, when relevant, you should use to construct your answer. You may also see image descriptions from images uploaded by the user. Prioritize image descriptions, when helpful, to construct your answer.
  Integrate relevant information from these documents, ensuring each reference is linked to the document's number.
  Your response should be semi-formal. 
  When quoting directly, cite with footnotes linked to the document number and page number, if provided. 
  Summarize or paraphrase other relevant information with inline citations, again referencing the document number and page number, if provided.
  If the answer is not in the provided documents, state so. Yet always provide as helpful a response as possible to directly answer the question.
  Conclude your response with a LIST of the document titles as clickable placeholders, each linked to its respective document number and page number, if provided.
  Always share page numbers if they were shared with you.
  ALWAYS follow the examples below:
  Insert an inline citation like this in your response: 
  "[1]" if you're referencing the first document or 
  "[1, page: 2]" if you're referencing page 2 of the first document.
  At the end of your response, list the document title with a clickable link, like this: 
  "1. [document_name](#)" if you're referencing the first document or
  "1. [document_name, page: 2](#)" if you're referencing page 2 of the first document.
  Nothing else should prefixxed or suffixed to the citation or document name. 

  Consecutive inline citations are ALWAYS discouraged. Use a maximum of 3 citations. Follow this exact formatting: separate citations with a comma like this: "[1, page: 2], [2, page: 3]" or like this "[1], [2], [3]".

  Suppose a document name is shared with you along with the index and pageNumber below like "27: www.pdf, page: 2", "28: www.osd", "29: pdf.www, page 11
  15" where 27, 28, 29 are indices, www.pdf, www.osd, pdf.www are document_name, and 2, 11 are the pageNumbers and 15 is the content of the document, then inline citations and final list of cited documents should ALWAYS be in the following format:
  ```
  The sky is blue. [27, page: 2][28] The grass is green. [29, page: 11]
  Relevant Sources:

  27. [www.pdf, page: 2](#)
  28. [www.osd](#)
  29. [pdf.www, page: 11](#)
  ```
  ONLY return the documents with relevant information and cited in the response. If there are no relevant sources, don't include the "Relevant Sources" section in response.
  The user message will include excerpts from the high-quality documents, APIs/tools, and image descriptions to construct your answer. Each will be labeled with XML-style tags, like <Potentially Relevant Documents> and <Tool Ouputs>. Make use of that information when writing your response."""

userPrompt = """
  Here's high quality passages from the user's documents. Use these, and cite them carefully in the format previously described, to construct your answer:
  <Potentially Relevant Documents>
  1: assignment-959384
  This is created as a reminder that two comments on the weekly discussion forum are due on sunday at midnight. No submission or grade in this assignment. This is just a reminder. 
  Please go to the weekly discussion form for giving the responses.
  ---
  2: assignment-959381
  This is created as a reminder that two comments on the weekly discussion forum are due on Sunday at midnight. No submission or grade in this assignment. This is just a reminder. 
  Please go to the weekly discussion forum for giving the responses.
  ---
  3: assignment-959388
  This is created as a reminder that two comments on the weekly discussion forum are due on Sunday at midnight. No submission or grade in this assignment. This is just a reminder. 
  Please go to the weekly discussion forum for giving the responses.
  ---
  4: assignment-959380
  This is created as a reminder that two comments on the weekly discussion forum are due on sunday at midnight. No submission or grade in this assignment. This is just a reminder. 
  Please go to the weekly discussion forum for giving the responses.
  ---
  5: Weekly-Live-Session-Forum
  Please submit your questions by 12:00PM on the day of the live session. Questions can cover this week's readings, videos, discussion, assignments, or anything else related to this week's topicsSubject line example: Week # Question
  ---
  6: assignment-959386
  Week 4 Discussion Comments Reminder
  This is created as a reminder that two comments on the weekly discussion forum are due on sunday at midnight. No submission or grade in this assignment. This is just a reminder. 
  Please go to the weekly discussion form for giving the responses.
  ---
  7: syllabus
  The Syllabus and other details are part of the orientation module.
  ---
  8: Q-A-Discussion-Board
  Please use this forum for any questions you might have for the instructor about the course. You're welcome to respond to your peers as well. If you send an email to your instructor that may benefit the class, he or she may ask you to post the question here before the instructor will respond. You can subscribe to this forum to get email alerts when new questions are posted or answered. Personal or grade-related questions should be emailed directly to your instructor.
  ---
  9: assignment-959373
  Submit Project Ideas here and the keywords you want data for from Brand24. The data will be provided here by the TA, as a reply to your post. If you need to change your keywords, just post a reply to the TA's post. Review details in the Final ProjectRequirements1. 50-100 words specifying the brand, the campaign, and at least two secondary sources that provide some context for your project idea. 2. The keywords you want data for. You can specify the keywords you want, as well as the keywords to exclude. Review the Brand24 video demo to understand how keywords get used.
  ---
  10: Project-Idea-Discussion
  Submit Project Ideas here and the keywords you want data for from Brand24. The data will be provided here by the TA, as a reply to your post. If you need to change your keywords, just post a reply to the TA's post. Review details in the Final ProjectRequirements1. 50-100 words specifying the brand, the campaign, and at least two secondary sources that provide some context for your project idea. 2. The keywords you want data for. You can specify the keywords you want, as well as the keywords to exclude. Review the Brand24 video demo to understand how keywords get used.
  ---
  11: Tech-Support-Forum
  Please use this forum for reporting any issues with tools used in the course.
  ---
  12: Share-Resources-with-others
  Many of you will be researching and reading outside the course readings, and I would be surprised if you are not. If you find some great resources/tutorials, do share them here, and explain what you like about them. Helping each other learn is a very important part of the learning experience.
  ---
  13: assignment-959374
  Discussion AssignmentOverviewIn this module, we review the challenges of working with big data, get some insights on techniques for text analysis, and take a deep dive into sentiment analysis with social data. In this discussion, we will consider trends highlighted in the US Consumer Trends report by Crimson Hexagon and use that knowledge to come up ideas for new products to leverage these trends. ObjectivesUnderstand how text analytics can lead to important insights.See the business value of analyzing unstructured data from social platforms.Create new product/service ideas based on the insights from unstructured data.Share your assessments to help others learn.Time EstimateApproximately 2 hoursAssignment InstructionsDiscussion PromptIn your initial post, follow the directions and answer the prompts:Review the reading "US Consumer Trends Report" by Crimson Hexagon. (Focus particularly on the detailed consumer profiles within the sectors discussed in the report.It has many sectors mentioned. Think of yourself as an new entrant(entrepreneur) or a current business in one of these sectors. Pick one sector and a role – entrepreneur or current business.For this one sector, review the trends highlighted and answer the prompts below, based on the role.Entrepreneur – If you take the role of an entrepreneur: What new product or service would you recommend based on the insights presented for this sector?If there is evidence of the appropriate target demographic or market size that can be inferred from the analysis, do mention that.What specific insights are you leveraging from social data that have informed you of what your new product or service idea can be?Is there any insight on the kind of branding or messaging you can focus on while launching your product/service?Any other insights in the report that help inform a successful launch of your product/service, once you identify it?Current Business – If you take the role of a current business (put yourself in the shoes of one of the firms mentioned in the analysis. If no firm is mentioned, think of yourself as an existing provider of the product or services):Describe your business.What changes would you make to your existing product or services to leverage the trends highlighted or counter new competition, highlighted in the reports?What specific insights led you to suggest the changes above?Is there any insight on the kind of branding or messaging that you can adopt to make your existing product or service more successful?Any other insights in the report that will help you fight the new or current competition?Utilize ChatGPT to brainstorm initial product ideas and refine them based on the interactions or to evaluate potential business adjustments or marketing strategies. Upload the consumer trends report to ChatGPT for better answers. Discuss how insights from social data presented in the report influenced your decisions. Use ChatGPT to validate these insights or explore further data points.As always, use ChatGPT as a brainstorming partner and check what it comes up with. Initial PostYou must submit an initial post for this activity. Compose an initial post that meets the following requirements:Word range – 500 words (plus or minus 10% words), excluding referencesTitle your post with the proposed product/service/firm.Use ChatGPT to assist in compiling research, generating ideas, and performing quick analyses.Include a brief dialogue or summary of your ChatGPT session to showcase how it influenced your product development process.Include a link to the ChatGPT transcript at the end of your post. Response PostsAfter your classmates have posted, read and respond to at least TWO of their posts. Each of your response posts must meet the following requirements:Word Range – 100 words (plus or minus 10% words), excluding references (if any)The response should seek to stimulate more in-depth discussion and learning among the larger groupGradingThe initial post is worth 12 pointsReply posts are worth 8 points (4 points per reply)
  ---
  14: Week-3-Discussion
  Discussion AssignmentOverviewIn this module, we review the challenges of working with big data, get some insights on techniques for text analysis, and take a deep dive into sentiment analysis with social data. In this discussion, we will consider trends highlighted in the US Consumer Trends report by Crimson Hexagon and use that knowledge to come up ideas for new products to leverage these trends. ObjectivesUnderstand how text analytics can lead to important insights.See the business value of analyzing unstructured data from social platforms.Create new product/service ideas based on the insights from unstructured data.Share your assessments to help others learn.Time EstimateApproximately 2 hoursAssignment InstructionsDiscussion PromptIn your initial post, follow the directions and answer the prompts:Review the reading "US Consumer Trends Report" by Crimson Hexagon. (Focus particularly on the detailed consumer profiles within the sectors discussed in the report.It has many sectors mentioned. Think of yourself as an new entrant(entrepreneur) or a current business in one of these sectors. Pick one sector and a role – entrepreneur or current business.For this one sector, review the trends highlighted and answer the prompts below, based on the role.Entrepreneur – If you take the role of an entrepreneur: What new product or service would you recommend based on the insights presented for this sector?If there is evidence of the appropriate target demographic or market size that can be inferred from the analysis, do mention that.What specific insights are you leveraging from social data that have informed you of what your new product or service idea can be?Is there any insight on the kind of branding or messaging you can focus on while launching your product/service?Any other insights in the report that help inform a successful launch of your product/service, once you identify it?Current Business – If you take the role of a current business (put yourself in the shoes of one of the firms mentioned in the analysis. If no firm is mentioned, think of yourself as an existing provider of the product or services):Describe your business.What changes would you make to your existing product or services to leverage the trends highlighted or counter new competition, highlighted in the reports?What specific insights led you to suggest the changes above?Is there any insight on the kind of branding or messaging that you can adopt to make your existing product or service more successful?Any other insights in the report that will help you fight the new or current competition?Utilize ChatGPT to brainstorm initial product ideas and refine them based on the interactions or to evaluate potential business adjustments or marketing strategies. Upload the consumer trends report to ChatGPT for better answers. Discuss how insights from social data presented in the report influenced your decisions. Use ChatGPT to validate these insights or explore further data points.As always, use ChatGPT as a brainstorming partner and check what it comes up with. Initial PostYou must submit an initial post for this activity. Compose an initial post that meets the following requirements:Word range – 500 words (plus or minus 10% words), excluding referencesTitle your post with the proposed product/service/firm.Use ChatGPT to assist in compiling research, generating ideas, and performing quick analyses.Include a brief dialogue or summary of your ChatGPT session to showcase how it influenced your product development process.Include a link to the ChatGPT transcript at the end of your post. Response PostsAfter your classmates have posted, read and respond to at least TWO of their posts. Each of your response posts must meet the following requirements:Word Range – 100 words (plus or minus 10% words), excluding references (if any)The response should seek to stimulate more in-depth discussion and learning among the larger groupGradingThe initial post is worth 12 pointsReply posts are worth 8 points (4 points per reply)
  ---
  15: assignment-959376
  Discussion AssignmentOverviewIn this module, we looked at some frameworks to use in the process of data visualization. This discussion will focus on looking at some visualizations made by others and you will evaluate them and apply some of the concepts in this module. This will help set you up for the upcoming assignment for this module as well.ObjectivesLearn by Evaluating and critiquing VisualizationsApply concepts learned in this module Share your assessments to help others learn Time EstimateApproximately 2 hoursAssignment InstructionsDiscussion PromptIn your initial post, follow the directions and then answer the prompts below:Pick two of the authors from this list https://public.tableau.com/en-us/s/authors#!/   Review their visualizations, by clicking on the 'View Profile link. For each author, you select, pick one visualization that you find most interestingWatch the first 20 minutes of this video to get insights into good chartsAnswer the following prompts in your post. Include a clickable hyperlink in your post (how to make a hyperlink in a post) for each visualization(two authors, one visualization each) What is the objective of the visualization?What is the main conclusion you draw from the visualization? What do you learn? What is the classification and why do you think so( Declarative or Exploratory and Data-Driven or Conceptual) What is one thing that could be improved? What is one thing the author does extremely well?Initial PostYou must submit an initial post for this activity. Compose an initial post that meets the following requirements:Word range - 350 words (plus or minus 10% words), excluding references.Uses the visualization title/subject(can be shortened)  as the subject of your post.Response PostsAfter your classmates have posted, read, and respond to at least TWO of their posts. Each of your response posts must meet the following requirements:Word Range- 100 words (plus or minus 10% words), excluding references(if any).Stimulate more in-depth discussion and learning among the larger group.Submission DirectionsInitial PostTo submit your initial post, click on the Reply button below.Compose your post and click Submit. RepliesClick on the title of a classmate's postClick ReplyCompose your response post and click SubmitRepeat to compose additional response postsCompose your post and click Submit.GradingThe initial post is worth 12 pointsReply posts are worth 8 points (4 points per reply)Subscribe to the ForumTo subscribe to the forum and receive notifications, click on the Subscribe button at the top of the new page.
  ---
  16: Week-2-Discussion
  Discussion AssignmentOverviewIn this module, we looked at some frameworks to use in the process of data visualization. This discussion will focus on looking at some visualizations made by others and you will evaluate them and apply some of the concepts in this module. This will help set you up for the upcoming assignment for this module as well.ObjectivesLearn by Evaluating and critiquing VisualizationsApply concepts learned in this module Share your assessments to help others learn Time EstimateApproximately 2 hoursAssignment InstructionsDiscussion PromptIn your initial post, follow the directions and then answer the prompts below:Pick two of the authors from this list https://public.tableau.com/en-us/s/authors#!/   Review their visualizations, by clicking on the 'View Profile link. For each author, you select, pick one visualization that you find most interestingWatch the first 20 minutes of this video to get insights into good chartsAnswer the following prompts in your post. Include a clickable hyperlink in your post (how to make a hyperlink in a post) for each visualization(two authors, one visualization each) What is the objective of the visualization?What is the main conclusion you draw from the visualization? What do you learn? What is the classification and why do you think so( Declarative or Exploratory and Data-Driven or Conceptual) What is one thing that could be improved? What is one thing the author does extremely well?Initial PostYou must submit an initial post for this activity. Compose an initial post that meets the following requirements:Word range - 350 words (plus or minus 10% words), excluding references.Uses the visualization title/subject(can be shortened)  as the subject of your post.Response PostsAfter your classmates have posted, read, and respond to at least TWO of their posts. Each of your response posts must meet the following requirements:Word Range- 100 words (plus or minus 10% words), excluding references(if any).Stimulate more in-depth discussion and learning among the larger group.Submission DirectionsInitial PostTo submit your initial post, click on the Reply button below.Compose your post and click Submit. RepliesClick on the title of a classmate's postClick ReplyCompose your response post and click SubmitRepeat to compose additional response postsCompose your post and click Submit.GradingThe initial post is worth 12 pointsReply posts are worth 8 points (4 points per reply)Subscribe to the ForumTo subscribe to the forum and receive notifications, click on the Subscribe button at the top of the new page.
  ---
  17: AI-use-in-education
  A discussion forum to help us leverage AI to augment our intelligence.
  ---
  18: assignment-959377
  OverviewIn this module, we discussed a framework to analyze customer interactions in the form of a journey. The article "Competing on Customer Journeys" outlines the four capabilities firms need to develop to shape these journeys and build a loyal customer base. In this assignment, you will discuss the role of analytics in enabling these four capabilities, find an example of a firm that has developed one or more of these capabilities, and map out where in the customer journey they apply this capability.ObjectivesUnderstand the four capabilities central to innovation in the Consumer Decision Journey (CDJ).Understand the role of analytics in executing these capabilities.Identify a capability in a current example based on experience or research.Identify the stage in the CDJ where the capability is applied.Time Estimate2 hours (assuming completion of readings and videos)Assignment InstructionsDiscussion PromptExplain how analytics underlies the four capabilities discussed in the article. Use examples from the readings.Do research on the web or use ChatGPT (free account) to identify and analyze a recent example of a brand, product, or service that effectively demonstrates one of the four capabilities in practice. Ensure your examples are current and distinct from any materials covered in the course or readings.Tip: To facilitate more insightful results from ChatGPT, begin the conversation by uploading the Week 1 lecture PDF and proceed with the discussion prompts accordingly.Specify the stage in the Consumer Decision Journey (CDJ) where the identified capability is applied, using insights from ChatGPT to deepen your analysis and validate with credible sources.Initial PostWord range: 350 words (plus or minus 10%), excluding references.Subject of your post: Use the capability followed by the brand/product/service (e.g., "Automating Customer Marketing at Spotify").Validate the information provided by ChatGPT before submitting your post and cite the sources that support your findings.Submit a link to your ChatGPT transcript along with your discussion post.Response PostsAfter submitting your initial post, engage in peer review by providing constructive feedback on at least two of your classmates’ posts. This will help enhance your critical thinking and expose you to different perspectives.Word range for each response post: 100 words (plus or minus 10%), excluding references (if any).GradingThe initial post is worth 12 points.Reply posts are worth 8 points (4 points per reply).Example Instructions for Using ChatGPTStep-by-Step InstructionsOpen a ChatGPT Session: Instructions for using ChatGPT 4oStart a conversation with ChatGPT and provide context about the assignment. For example: "I'm working on an assignment about the Consumer Decision Journey and need examples of brands demonstrating key capabilities such as automation, proactive personalization, contextual interaction, and journey innovation." Upload the slide deck for the lecture and give the link to the Mckinsey article as part of the context to the chatbot. Ask Specific Questions:For each capability, ask ChatGPT for recent examples. Example prompt: "Can you give me a recent example of a company that uses automation in their customer journey?". You should have at least four different examples, one for each capability. You can even ask ChatGPT to work with a brand that you are familiar with/use often to have it evaluate for these capabiltiies.Analyze Responses:Review the examples provided by ChatGPT and select ones that are relevant and distinct from those covered in your course materials. Conduct Validation:Search for secondary sources (e.g., articles, case studies) to validate the examples provided by ChatGPT. Ensure that your examples are accurate and up-to-date.Document Findings:Compile your findings, and write the post as described above. Cite your sources.
  ---
  19: Week-1-Discussion
  OverviewIn this module, we discussed a framework to analyze customer interactions in the form of a journey. The article "Competing on Customer Journeys" outlines the four capabilities firms need to develop to shape these journeys and build a loyal customer base. In this assignment, you will discuss the role of analytics in enabling these four capabilities, find an example of a firm that has developed one or more of these capabilities, and map out where in the customer journey they apply this capability.ObjectivesUnderstand the four capabilities central to innovation in the Consumer Decision Journey (CDJ).Understand the role of analytics in executing these capabilities.Identify a capability in a current example based on experience or research.Identify the stage in the CDJ where the capability is applied.Time Estimate2 hours (assuming completion of readings and videos)Assignment InstructionsDiscussion PromptExplain how analytics underlies the four capabilities discussed in the article. Use examples from the readings.Do research on the web or use ChatGPT (free account) to identify and analyze a recent example of a brand, product, or service that effectively demonstrates one of the four capabilities in practice. Ensure your examples are current and distinct from any materials covered in the course or readings.Tip: To facilitate more insightful results from ChatGPT, begin the conversation by uploading the Week 1 lecture PDF and proceed with the discussion prompts accordingly.Specify the stage in the Consumer Decision Journey (CDJ) where the identified capability is applied, using insights from ChatGPT to deepen your analysis and validate with credible sources.Initial PostWord range: 350 words (plus or minus 10%), excluding references.Subject of your post: Use the capability followed by the brand/product/service (e.g., "Automating Customer Marketing at Spotify").Validate the information provided by ChatGPT before submitting your post and cite the sources that support your findings.Submit a link to your ChatGPT transcript along with your discussion post.Response PostsAfter submitting your initial post, engage in peer review by providing constructive feedback on at least two of your classmates’ posts. This will help enhance your critical thinking and expose you to different perspectives.Word range for each response post: 100 words (plus or minus 10%), excluding references (if any).GradingThe initial post is worth 12 points.Reply posts are worth 8 points (4 points per reply).Example Instructions for Using ChatGPTStep-by-Step InstructionsOpen a ChatGPT Session: Instructions for using ChatGPT 4oStart a conversation with ChatGPT and provide context about the assignment. For example: "I'm working on an assignment about the Consumer Decision Journey and need examples of brands demonstrating key capabilities such as automation, proactive personalization, contextual interaction, and journey innovation." Upload the slide deck for the lecture and give the link to the Mckinsey article as part of the context to the chatbot. Ask Specific Questions:For each capability, ask ChatGPT for recent examples. Example prompt: "Can you give me a recent example of a company that uses automation in their customer journey?". You should have at least four different examples, one for each capability. You can even ask ChatGPT to work with a brand that you are familiar with/use often to have it evaluate for these capabiltiies.Analyze Responses:Review the examples provided by ChatGPT and select ones that are relevant and distinct from those covered in your course materials. Conduct Validation:Search for secondary sources (e.g., articles, case studies) to validate the examples provided by ChatGPT. Ensure that your examples are accurate and up-to-date.Document Findings:Compile your findings, and write the post as described above. Cite your sources.
  ---
  20: Week-4-Discussion
  OverviewGeolocation data is invaluable for providing spatial context to business strategies, enabling precise targeting, and uncovering location-based trends and patterns. It empowers businesses to make data-driven decisions, optimize operations, and enhance customer experiences by understanding and leveraging the geographical dimensions of their data.This discussion directs your attention to current use cases of geo-location data analysis and visualization by firms for strategic decision-making, with a focus on marketing/branding. ObjectivesUnderstand how geo-map visualizations are used as a tool to analyze and derive insights from marketing data.Identify a use case where map visualizations can assist in making marketing decisions. Use Tableau visualizations for data-driven decision-making.Time EstimateApproximately 2 -3 hoursAssignment InstructionsBefore you start your research, think about the following questions a. What are the potential benefits of using geo-map visualizations for analyzing marketing data?b. How can geo-map visualizations help us understand customer behavior or preferences based on geographical data?c. What marketing insights or patterns can we potentially discover through geo-map visualizations?d. How can we effectively transform raw marketing data into actionable geo map visualizations?Feed these questions into ChatGPT one by one, and explore the topic. Do not copy/paste all of them together. Now, find some real-world examples where businesses have successfully used geo-map visualizations for marketing/branding analysis and decision-making and follow the instructions below. Check the websites of companies like EsriLinks to an external site., TableauLinks to an external site., or other major providers of mapping and data visualization solutions, as they often feature case studies highlighting successful implementations. You can search for keywords like "marketing," "branding," or specific industries to find relevant examples. You can also browse the success stories by industry using Analytics Solutions for Industries | TableauLinks to an external site..  Your initial post should meet the following requirements:Research and select a firm/product/brand of your choice that utilizes geographic data or has a significant geographic component in its operations, such as retail chains, delivery services, tourism companies, or any other brand that benefits from analysis using location-based data. You can focus on marketing use cases. Provide your commentary/ insights on how the brand can leverage the geo-map visualizations to gain insights and make strategic decisions. Discuss any limitations or challenges that could be faced during the data visualization process and propose potential improvements/alternative approaches.You are free to use visuals, graphs, or any other suitable media to support your discussion (optional).Chare the ChatGPT transcript at the end of your post. Cite your sources. This is not part of the word limitInitial PostYou must submit an initial post for this activity. Compose an initial post that meets the following requirements:Word range - 350 words (plus or minus 10% words), excluding references.Uses your name and the capability along with brand/product/service as the subject of your post (for example, Robert Smith: automating customer marketing at Spotify). Response PostsAfter your classmates have posted, read and respond to at least two of their posts. Each of your response posts must meet the following requirements:Word Range- 100 words (plus or minus 10% words), excluding references(if any).Stimulate more in-depth discussion and learning among the larger group. GradingThe initial post is worth 12 pointsReply posts are worth 8 points (4 points per reply)
  ---
  21: assignment-959372
  OverviewGeolocation data is invaluable for providing spatial context to business strategies, enabling precise targeting, and uncovering location-based trends and patterns. It empowers businesses to make data-driven decisions, optimize operations, and enhance customer experiences by understanding and leveraging the geographical dimensions of their data.This discussion directs your attention to current use cases of geo-location data analysis and visualization by firms for strategic decision-making, with a focus on marketing/branding. ObjectivesUnderstand how geo-map visualizations are used as a tool to analyze and derive insights from marketing data.Identify a use case where map visualizations can assist in making marketing decisions. Use Tableau visualizations for data-driven decision-making.Time EstimateApproximately 2 -3 hoursAssignment InstructionsBefore you start your research, think about the following questions a. What are the potential benefits of using geo-map visualizations for analyzing marketing data?b. How can geo-map visualizations help us understand customer behavior or preferences based on geographical data?c. What marketing insights or patterns can we potentially discover through geo-map visualizations?d. How can we effectively transform raw marketing data into actionable geo map visualizations?Feed these questions into ChatGPT one by one, and explore the topic. Do not copy/paste all of them together. Now, find some real-world examples where businesses have successfully used geo-map visualizations for marketing/branding analysis and decision-making and follow the instructions below. Check the websites of companies like EsriLinks to an external site., TableauLinks to an external site., or other major providers of mapping and data visualization solutions, as they often feature case studies highlighting successful implementations. You can search for keywords like "marketing," "branding," or specific industries to find relevant examples. You can also browse the success stories by industry using Analytics Solutions for Industries | TableauLinks to an external site..  Your initial post should meet the following requirements:Research and select a firm/product/brand of your choice that utilizes geographic data or has a significant geographic component in its operations, such as retail chains, delivery services, tourism companies, or any other brand that benefits from analysis using location-based data. You can focus on marketing use cases. Provide your commentary/ insights on how the brand can leverage the geo-map visualizations to gain insights and make strategic decisions. Discuss any limitations or challenges that could be faced during the data visualization process and propose potential improvements/alternative approaches.You are free to use visuals, graphs, or any other suitable media to support your discussion (optional).Chare the ChatGPT transcript at the end of your post. Cite your sources. This is not part of the word limitInitial PostYou must submit an initial post for this activity. Compose an initial post that meets the following requirements:Word range - 350 words (plus or minus 10% words), excluding references.Uses your name and the capability along with brand/product/service as the subject of your post (for example, Robert Smith: automating customer marketing at Spotify). Response PostsAfter your classmates have posted, read and respond to at least two of their posts. Each of your response posts must meet the following requirements:Word Range- 100 words (plus or minus 10% words), excluding references(if any).Stimulate more in-depth discussion and learning among the larger group. GradingThe initial post is worth 12 pointsReply posts are worth 8 points (4 points per reply)

  </Potentially Relevant Documents>

  Finally, please respond to the user's query to the best of your ability:
  <User Query>
  What is the late submission policy
  </User Query>"""


def run_chat():
  client = Client(host='https://ollama.ncsa.ai')
  start_time = time.time()
  response = client.chat(model='llama3.1:70b',
                         messages=[
                             {
                                 'role': 'system',
                                 'content': systemPrompt,
                                 'role': 'user',
                                 'content': userPrompt,
                             },
                         ])
  end_time = time.time()
  duration = end_time - start_time
  tokens_per_second = response['eval_count'] / duration
  return tokens_per_second


def run_parallel_chats(num_chats):
  with ProcessPoolExecutor() as executor:
    futures = [executor.submit(run_chat) for _ in range(num_chats)]
    results = [future.result() for future in as_completed(futures)]
  return sum(results) / len(results)  # Average tokens per second


def main():
  max_chats = 100
  results = []

  try:
    for num_chats in range(1, max_chats + 1):
      try:
        print(f"Running {num_chats} simultaneous chats...")
        avg_tokens_per_second = run_parallel_chats(num_chats)
        results.append((num_chats, avg_tokens_per_second))
        print(f"Average tokens per second: {avg_tokens_per_second:.2f}")
      except Exception as e:
        print(f"Error occurred at {num_chats} chats: {str(e)}")
        break
  except KeyboardInterrupt:
    print("\nExecution interrupted. Generating graph with collected data...")

  if not results:
    print("No data collected. Unable to generate graph.")
    return

  # Create the bar graph
  chats, tokens_per_second = zip(*results)
  plt.figure(figsize=(12, 6))
  plt.bar(chats, tokens_per_second)
  plt.xlabel('Number of Simultaneous Chats')
  plt.ylabel('Average Tokens per Second')
  plt.title('Ollama Server Performance Under Load - Long prompt, 70b')
  plt.savefig('ollama_performance-long-prompt-70b.png')
  plt.close()

  print("Test completed. Results saved to 'ollama_performance.png'")


if __name__ == "__main__":
  main()
