"""This final verifier intends to verify the formal output, and we use LangChain to parse the result"""
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain.prompts import PromptTemplate, ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAIdef 
def filter_context(self, context, user_query):
    prompt_template = PromptTemplate.from_template(
        "<|system|>\n"
        "{system_prompt}\n"
        "<|user|>\n"
        "{user_prompt}\n"
        "<|assistant|>\n"

    )

    # You are a factual summarizer of partial documents. Stick to the facts (including partial info when necessary to avoid making up potentially incorrect details), and say I don't know when necessary.
    # Provide a comprehensive summary of the given text, based on this question:\n{doc.page_content}\nQuestion: {user_question}\nThe summary should cover all the key points that are relevant to the question, while also condensing the information into a concise format. The length of the summary should be as short as possible, without losing relevant information.\nMake use of direct quotes from the text.\nFeel free to include references, sentence fragments, keywords or anything that could help someone learn about it, only as it relates to the given question.\nIf the text does not provide information to answer the question, please write 'None' and nothing else.
    # --
    # system_prompt="You are concise, and only give the user exactly what they asking for. Follow instructions precisely and do not say anything extra.",
    # user_prompt="Say 'False' and nothing else. Do not include any filler language, reply with just 'False' Go:",
    final_prompt = prompt_template.format(
        system_prompt="""You are an expert at determining if a passage is relevant and helpful for answering a question.
        To be valuable, a passage must have at least some amount of useful and meaningful information with more than a passing mention of the topic.
        As part of your thinking process, you first write a few sentences evaluating the utility of the passage, given the question we're trying to answer.
        Finally, you must submit your final answer by adding two newline characters then \"Yes.\" or \"No.\" or \"I don't know.\". Provide a single answer only. Providing multiple final results will disqualify you.
        Here's a template code snippit of how it should work (with placeholder variables):
        ```
        Passage: <The full text of the passage>
        Question: <The question we're using to determine relevancy of the passage>
        Your evaluation of the utility of the passage: <A few sentences exploring how useful the passage is for this particular question>
        Final answer: <Enter one of \"Yes.\" or \"No.\" or \"I don't know.\"
        ```
        Here's a complete example. Follow this formatting exactly.
        ```
        Passage: Figure 4.6: Overview of the CUDA device memory model 
         
        In order to fully appreciate the difference between registers, shared memory and global memory, we need to go into a little more details of how these different memory types are realized and used in modern processors. Virtually all modern processors find their root in the model proposed by John von Neumann in 1945, which is shown in Figure 4.7. The CUDA devices are no exception. The Global Memory in a CUDA device maps to the Memory box in Figure 4.7. The processor box corresponds to the processor chip boundary that we typically see today. The Global Memory is off the processor chip and is implemented with DRAM technology, which implies long access latencies and relatively low access bandwidth. The Registers correspond to the Register File of the von Neumann model. The Register File is on the processor chip, which implies very short access latency and drastically higher access bandwidth when compared to the global memory.
        Question: Explain how tiling helps with global memory bandwidth.
        Your evaluation of the utility of the passage: The passage briefly mentions the use of shared memory as a means to reduce global memory bandwidth, but it doesn't provide a detailed explanation or analysis of how tiling helps with global memory bandwidth. Therefore, the passage is not helpful when answering the question.
        Final answer: No.
        ```""",
        user_prompt=("Passage: "
                    f"{context['text']}\n"
                    "Question: "
                    f"{user_query}\n"
                    "Your evaluation of the utility of the passage: "
                    ),  
      
    )
    output_parser = StructuredOutputParser.from_response_schemas(final_prompt)
    format_instructions = output_parser.get_format_instructions()
    prompt = PromptTemplate(
    partial_variables={"format_instructions": format_instructions}
)
    # print(f"-------\nfinal_prompt:\n{final_prompt}\n^^^^^^^^^^^^^")
    try: 
      completion = run_model(prompt)
      return {"completion": completion, "context": context}
    except Exception as e: 
      print(f"Error: {e}")

def parse_result(result):
    output.parser.parse(result)
