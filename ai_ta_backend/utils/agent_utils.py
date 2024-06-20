import json
# from ai_ta_backend.model.response import FunctionMessage, ToolInvocation
from dotenv import load_dotenv
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_openai import ChatOpenAI, OpenAI
from langchain_community.agent_toolkits import create_sql_agent
from langchain_core.prompts import (
		ChatPromptTemplate,
		FewShotPromptTemplate,
		MessagesPlaceholder,
		PromptTemplate,
		SystemMessagePromptTemplate,
)
import os
import logging
from flask_sqlalchemy import SQLAlchemy

from langchain_openai import ChatOpenAI

from operator import itemgetter

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain_community.agent_toolkits import create_sql_agent
from langchain.tools import BaseTool, StructuredTool, Tool, tool
import random
from langgraph.prebuilt.tool_executor import ToolExecutor
from langchain.tools.render import format_tool_to_openai_function


from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage

from langchain_core.agents import AgentFinish
from langgraph.prebuilt import ToolInvocation
import json
from langchain_core.messages import FunctionMessage
from langchain_community.utilities import SQLDatabase
from langchain_community.vectorstores import FAISS
from langchain_core.example_selectors import SemanticSimilarityExampleSelector
from langchain_openai import OpenAIEmbeddings



def get_dynamic_prompt_template():
		
		examples = [
		{
				"input": "How many accepted names are only distributed in Karnataka?",
				"query": 'SELECT COUNT(*) as unique_pairs_count FROM (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "DB" AND ("Additional_Details_2" LIKE "Karnataka%"));'
		},
		{
				"input": "How many names were authored by Roxb?",
				"query": 'SELECT COUNT(*) as unique_pairs_count FROM (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Author_Name" LIKE "%Roxb%" AND "Record_Type_Code" IN ("AN", "SN"));'
		},
		{
				"input": "How many species have distributions in Myanmar, Meghalaya and Andhra Pradesh?",
				"query": 'SELECT COUNT(*) FROM (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "DB" AND ("Additional_Details_2" LIKE "%Myanmar%" AND Additional_Details_2 LIKE "%Meghalaya%" AND "Additional_Details_2" LIKE "%Andhra Pradesh%"));'
		},
		{
				"input": "List the accepted names common to Myanmar, Meghalaya, Odisha, Andhra Pradesh.",
				"query": 'SELECT DISTINCT Scientific_Name FROM plants WHERE ("Family_Number", "Genus_Number", "Accepted_name_number") IN (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "DB" AND ("Additional_Details_2" LIKE "%Myanmar%" AND Additional_Details_2 LIKE "%Meghalaya%" AND "Additional_Details_2" LIKE "%Odisha%" AND "Additional_Details_2" LIKE "%Andhra Pradesh%"));'
		},
		{
				"input": "List the accepted names that represent 'tree'.",
				"query": 'SELECT DISTINCT "Scientific_Name" FROM plants WHERE ("Family_Number", "Genus_Number", "Accepted_name_number") IN (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "HB" AND "Additional_Details_2" LIKE "%tree%");'
		},
		{
				"input": "List the accepted names linked with Endemic tag.",
				"query": 'SELECT DISTINCT "Scientific_Name" FROM plants WHERE ("Family_Number", "Genus_Number", "Accepted_name_number") IN (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "DB" AND "Additional_Details_2" LIKE "%Endemic%");'
		},
		{
				"input": "List the accepted names published in Fl. Brit. India [J. D. Hooker].",
				"query": 'SELECT DISTINCT "Scientific_Name" FROM plants WHERE "Record_Type_Code" in ("AN", "SN") AND ("Publication" LIKE "%Fl. Brit. India [J. D. Hooker]%" OR "Publication" LIKE "%[J. D. Hooker]%" OR "Publication" LIKE "%Fl. Brit. India%");'
		},
		{
				"input": "How many accepted names have ‘Silhet’/ ‘Sylhet’ in their Type?",
				"query": 'SELECT DISTINCT "Scientific_Name" FROM plants WHERE ("Family_Number", "Genus_Number", "Accepted_name_number") IN (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "TY" AND ("Additional_Details_2" LIKE "%Silhet%" OR "Additional_Details_2" LIKE "%Sylhet%"));'
		},
		{
				"input": "How many species were distributed in Sikkim and Meghalaya?",
				"query": 'SELECT COUNT(*) AS unique_pairs FROM (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "DB" AND ("Additional_Details_2" LIKE "%Sikkim%" AND Additional_Details_2 LIKE "%Meghalaya%"));'
		},
		{
				"input": "List the accepted names common to Kerala, Tamil Nadu, Andhra Pradesh, Karnataka, Maharashtra, Odisha, Meghalaya and Myanmar.",
				"query": 'SELECT DISTINCT "Scientific_Name" FROM plants WHERE ("Family_Number", "Genus_Number", "Accepted_name_number") IN (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "DB" AND ("Additional_Details_2" LIKE "%Myanmar%" AND Additional_Details_2 LIKE "%Meghalaya%" AND "Additional_Details_2" LIKE "%Odisha%" AND "Additional_Details_2" LIKE "%Andhra Pradesh%" AND "Additional_Details_2" LIKE "%Kerala%" AND "Additional_Details_2" LIKE "%Tamil Nadu%" AND "Additional_Details_2" LIKE "%Karnataka%" AND "Additional_Details_2" LIKE "%Maharashtra%"));'
		},
		{
				"input": "List the accepted names common to Europe, Afghanistan, Jammu & Kashmir, Himachal, Nepal, Sikkim, Bhutan, Arunachal Pradesh and China.",
				"query": 'SELECT DISTINCT "Scientific_Name" FROM plants WHERE ("Family_Number", "Genus_Number", "Accepted_name_number") IN (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "DB" AND ("Additional_Details_2" LIKE "%Europe%" AND Additional_Details_2 LIKE "%Afghanistan%" AND "Additional_Details_2" LIKE "%Jammu & Kashmir%" AND "Additional_Details_2" LIKE "%Himachal%" AND "Additional_Details_2" LIKE "%Nepal%" AND "Additional_Details_2" LIKE "%Sikkim%" AND "Additional_Details_2" LIKE "%Bhutan%" AND "Additional_Details_2" LIKE "%Arunachal Pradesh%" AND "Additional_Details_2" LIKE "%China%"));'
		},
		{
				"input": "List the accepted names common to Europe, Afghanistan, Austria, Belgium, Czechoslovakia, Denmark, France, Greece, Hungary, Italy, Moldava, Netherlands, Poland, Romania, Spain, Switzerland, Jammu & Kashmir, Himachal, Nepal, and China.",
				"query": 'SELECT DISTINCT "Scientific_Name" FROM plants WHERE ("Family_Number", "Genus_Number", "Accepted_name_number") IN (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "DB" AND ("Additional_Details_2" LIKE "%Europe%" AND Additional_Details_2 LIKE "%Afghanistan%" AND "Additional_Details_2" LIKE "%Jammu & Kashmir%" AND "Additional_Details_2" LIKE "%Himachal%" AND "Additional_Details_2" LIKE "%Nepal%" AND "Additional_Details_2" LIKE "%Austria%" AND "Additional_Details_2" LIKE "%Belgium%" AND "Additional_Details_2" LIKE "%Czechoslovakia%" AND "Additional_Details_2" LIKE "%China%" AND "Additional_Details_2" LIKE "%Denmark%" AND "Additional_Details_2" LIKE "%Greece%" AND "Additional_Details_2" LIKE "%France%" AND "Additional_Details_2" LIKE "%Hungary%" AND "Additional_Details_2" LIKE "%Italy%" AND "Additional_Details_2" LIKE "%Moldava%" AND "Additional_Details_2" LIKE "%Netherlands%" AND "Additional_Details_2" LIKE "%Poland%" AND "Additional_Details_2" LIKE "%Poland%" AND "Additional_Details_2" LIKE "%Romania%" AND "Additional_Details_2" LIKE "%Spain%" AND "Additional_Details_2" LIKE "%Switzerland%"));'
		},
		{
				"input": "List the species which are distributed in Sikkim and Meghalaya.",
				"query": 'SELECT DISTINCT "Scientific_Name" FROM plants WHERE ("Family_Number", "Genus_Number", "Accepted_name_number") IN (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "DB" AND ("Additional_Details_2" LIKE "%Sikkim%" AND Additional_Details_2 LIKE "%Meghalaya%"));'
		},
		{
				"input": "How many species are common to America, Europe, Africa, Asia, and Australia?",
				"query": 'SELECT COUNT(*) AS unique_pairs IN (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "DB" AND ("Additional_Details_2" LIKE "%America%" AND Additional_Details_2 LIKE "%Europe%" AND "Additional_Details_2" LIKE "%Africa%" AND "Additional_Details_2" LIKE "%Asia%" AND "Additional_Details_2" LIKE "%Australia%"));'
		},
		{
				"input": "List the species names common to India and Myanmar, Malaysia, Indonesia, and Australia.",
				"query": 'SELECT DISTINCT "Scientific_Name" FROM plants WHERE ("Family_Number", "Genus_Number", "Accepted_name_number") IN (SELECT DISTINCT "Family_Number","Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "DB" AND ("Additional_Details_2" LIKE "%India%" AND Additional_Details_2 LIKE "%Myanmar%" AND Additional_Details_2 LIKE "%Malaysia%" AND Additional_Details_2 LIKE "%Indonesia%" AND Additional_Details_2 LIKE "%Australia%"));'
		},
		{
				"input": "List all plants which are tagged as urban.",
				"query": 'SELECT DISTINCT "Scientific_Name" FROM plants WHERE "Record_Type_Code" IN ("AN", "SN") AND "Urban" = "YES";'
		},
		{
				"input": "List all plants which are tagged as fruit.",
				"query": 'SELECT DISTINCT "Scientific_Name" FROM plants WHERE "Record_Type_Code" IN ("AN", "SN") AND "Fruit" = "YES";'
		},
		{
				"input": "List all plants which are tagged as medicinal.",
				"query": 'SELECT DISTINCT "Scientific_Name" FROM plants WHERE "Record_Type_Code" IN ("AN", "SN") AND "Medicinal" = "YES";'
		},
		{
				"input": "List all family names which are gymnosperms.",
				"query": 'SELECT DISTINCT "Family_Name" FROM plants WHERE "Record_Type_Code" IN ("AN", "SN") AND "Groups" = "Gymnosperms";'
		},
		{
				"input": "How many accepted names are tagged as angiosperms?",
				"query": 'SELECT COUNT(DISTINCT "Scientific_Name") FROM plants WHERE "Record_Type_Code" IN ("AN", "SN") AND "Groups" = "Angiosperms";'
		},
		{
				"input": "How many accepted names belong to the 'Saxifraga' genus?",
				"query": 'SELECT COUNT(DISTINCT "Scientific_Name") FROM plants WHERE "Genus_Name" = "Saxifraga";'
		},
		{
				"input": "List the accepted names tagged as 'perennial herb' or 'climber'.",
				"query": 'SELECT DISTINCT "Scientific_Name" FROM plants WHERE ("Family_Number", "Genus_Number", "Accepted_name_number") IN (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "HB" AND ("Additional_Details_2" LIKE "%perennial herb%" OR "Additional_Details_2" LIKE "%climber%"));'
		},
		{
				"input": "How many accepted names are native to South Africa?",
				"query": 'SELECT COUNT(*) FROM plants WHERE ("Family_Number", "Genus_Number", "Accepted_name_number") IN (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "RE" AND "Additional_Details_2" LIKE "%native%" AND "Additional_Details_2" LIKE "%south%" AND "Additional_Details_2" LIKE "%africa%");'

		},
		{
				"input": "List the accepted names which were introduced and naturalized.",
				"query": 'SELECT DISTINCT "Scientific_Name FROM plants WHERE ("Family_Number", "Genus_Number", "Accepted_name_number") IN (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "RE" AND "Additional_Details_2" LIKE "%introduced%" AND "Additional_Details_2" LIKE "%naturalized%");'
		},
		{
				"input": "List all ornamental plants.",
				"query": 'SELECT DISTINCT "Scientific_Name FROM plants WHERE ("Family_Number", "Genus_Number", "Accepted_name_number") IN (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "RE" AND "Additional_Details_2" LIKE "%ornamental%");'
		},
		{
				"input": "How many plants from the 'Leguminosae' family have a altitudinal range up to 1000 m?",
				"query": 'SELECT COUNT(*) FROM plants WHERE "Record_Type_Code" = "AL" AND "Family_Name" = "Leguminosae" AND "Additional_Details_2" LIKE "%1000%";'
		},
		{
				"input": "List the accepted names linked with the 'endemic' tag for Karnataka.",
				"query": 'SELECT DISTINCT "Scientific_Name" FROM plants WHERE ("Family_Number", "Genus_Number", "Accepted_name_number") IN (SELECT DISTINCT "Family_Number", "Genus_Number", "Accepted_name_number" FROM plants WHERE "Record_Type_Code" = "DB" AND "Additional_Details_2" LIKE "%Endemic%" AND "Additional_Details_2" LIKE "%Karnataka%");'
		},
		{"input": "List all the accepted names under the family 'Gnetaceae'.",
		 "query": """
SELECT DISTINCT "Scientific_Name" FROM plants
JOIN (
		SELECT "Family_Number", "Genus_Number", "Accepted_name_number"
		FROM plants
		WHERE "Family_Number" IN (
				SELECT DISTINCT "Family_Number" FROM plants WHERE "Family_Name" = "Gnetaceae"
		)
) b
ON plants."Genus_Number" = b."Genus_Number" AND plants."Accepted_name_number" = b."Accepted_name_number" AND plants."Family_Number" = b."Family_Number"
WHERE plants."Record_Type_Code" = 'AN';
"""},
		{
				"input": "List all the accepted species that are introduced.",
				"query": """
SELECT DISTINCT "Scientific_Name" FROM plants
JOIN (
		SELECT "Family_Number", "Genus_Number", "Accepted_name_number"
		FROM plants
		WHERE "Record_Type_Code" = 'RE'and "Additional_Details_2" LIKE '%cultivated%'
) b
ON plants."Genus_Number" = b."Genus_Number" AND plants."Accepted_name_number" = b."Accepted_name_number" AND plants."Family_Number" = b."Family_Number"
WHERE plants."Record_Type_Code" = 'AN';
""",
		},
		{
				"input": "List all the accepted names with type 'Cycad'",
				"query": """
SELECT DISTINCT "Scientific_Name" FROM plants
JOIN (
		SELECT "Family_Number", "Genus_Number", "Accepted_name_number"
		FROM plants
		WHERE "Record_Type_Code" = 'HB'and "Additional_Details_2" LIKE '%Cycad%'

) b
ON plants."Genus_Number" = b."Genus_Number" AND plants."Accepted_name_number" = b."Accepted_name_number" AND plants."Family_Number" = b."Family_Number"
WHERE plants."Record_Type_Code" = 'AN';
""",
		},
		{
				"input": "List all the accepted names under the genus 'Cycas' with more than two synonyms.",
				"query": """
SELECT DISTINCT "Scientific_Name" FROM plants
JOIN (
		SELECT "Family_Number", "Genus_Number", "Accepted_name_number"
		FROM plants
		WHERE "Genus_Number" IN (
				SELECT DISTINCT "Genus_Number" FROM plants WHERE "Genus_Name" = 'Cycas'
		)
		AND "Family_Number" IN (
				SELECT DISTINCT "Family_Number" FROM plants WHERE "Genus_Name" = 'Cycas'
		)
		AND "Synonym_Number" > 2
) b
ON plants."Genus_Number" = b."Genus_Number" AND plants."Accepted_name_number" = b."Accepted_name_number" AND plants."Family_Number" = b."Family_Number"
WHERE plants."Record_Type_Code" = 'AN';
""",
		},
 {
				"input":'List all the accepted names published in Asian J. Conservation Biol.',
				"query": """
		SELECT DISTINCT "Scientific_Name"
		FROM plants
		WHERE "Record_Type_Code" = 'AN' AND "Publication" LIKE '%Asian J. Conservation Biol%';

""",
		},
 {
				"input": 'List all the accepted names linked with endemic tag.',
				"query": """
SELECT DISTINCT "Scientific_Name" FROM plants
JOIN (
		SELECT "Family_Number", "Genus_Number", "Accepted_name_number"
		FROM plants
		WHERE "Record_Type_Code" = 'DB'and "Additional_Details_2" LIKE '%Endemic%'

) b
ON plants."Genus_Number" = b."Genus_Number" AND plants."Accepted_name_number" = b."Accepted_name_number" AND plants."Family_Number" = b."Family_Number"
WHERE plants."Record_Type_Code" = 'AN';
""",
		},
 {
				"input": 'List all the accepted names that have no synonyms.' ,
				"query": """
SELECT  DISTINCT a."Scientific_Name" FROM plants a
group by a."Family_Number",a."Genus_Number",a."Accepted_name_number"
HAVING  SUM(a."Synonym_Number") = 0 AND a."Accepted_name_number" > 0;
""",
		},
 {
				"input": 'List all the accepted names authored by Roxb.',
				"query": """
SELECT "Scientific_Name"
FROM plants
WHERE "Record_Type_Code" = 'AN'AND "Author_Name" LIKE '%Roxb%';
""",
		},
 {
				"input": 'List all genera within each family',
				"query": """
SELECT "Family_Name", "Genus_Name"
FROM plants
WHERE "Record_Type_Code" = 'GE';
""",
		},
		 {
				"input": 'Did Minq. discovered Cycas ryumphii?',
				"query": """SELECT
		CASE
				WHEN EXISTS (
						SELECT 1
						FROM plants as a
						WHERE a."Scientific_Name" = 'Cycas rumphii'
						AND a."Author_Name" = 'Miq.'
				) THEN 'TRUE'
				ELSE 'FALSE'
		END AS ExistsCheck;
"""},

		]


		example_selector = SemanticSimilarityExampleSelector.from_examples(
				examples,
				OpenAIEmbeddings(),
				FAISS,
				k=5,
				input_keys=["input"],
				)


		prefix_prompt = """
		You are an agent designed to interact with a SQL database.
		Given an input question, create a syntactically correct SQLite query to run, then look at the results of the query and return the answer.
		You can order the results by a relevant column to return the most interesting examples in the database.
		Never query for all the columns from a specific table, only ask for the relevant columns given the question.
		You have access to tools for interacting with the database.
		Only use the given tools. Only use the information returned by the tools to construct your final answer.
		You MUST double check your query before executing it. If you get an error while executing a query, rewrite the query and try again.

		- Restrict your queries to the "plants" table.
		- Do not return more than {top_k} rows unless specified otherwise.
		- Add a limit of 25 at the end of SQL query.
		- If the SQLite query returns zero rows, return a message indicating the same.
		- Only refer to the data contained in the {table_info} table. Do not fabricate any data.
		- For filtering based on string comparison, always use the LIKE operator and enclose the string in `%`.
		- Queries on the `Additional_Details_2` column should use sub-queries involving `Family_Number`, `Genus_Number` and `Accepted_name_number`.

		Refer to the table description below for more details on the columns:
		1. **Record_Type_Code**: Contains text codes indicating the type of information in the row.
		- FA: Family Name, Genus Name, Scientific Name
		- TY: Type
		- GE: Genus Name
		- AN: Family Name (Accepted Name), Genus Name, Scientific Name, Author Name, Publication, Volume:Page, Year of Publication
		- HB: Habit
		- DB: Distribution/location of the plant
		- RE: Remarks
		- SN: Family Name (Synonym), Genus Name, Scientific Name, Author Name, Publication, Volume:Page, Year of Publication
		2. **Family_Name**: Contains the Family Name of the plant.
		3. **Genus_Name**: Contains the Genus Name of the plant.
		4. **Scientific_Name**: Contains the Scientific Name of the plant species.
		5. **Publication_Name**: Name of the journal or book where the plant discovery information is published. Use LIKE for queries.
		6. **Volume:_Page**: The volume and page number of the publication.
		7. **Year_of_Publication**: The year in which the plant information was published.
		8. **Author_Name**: May contain multiple authors separated by `&`. Use LIKE for queries.
		9. **Additional_Details**: Contains type, habit, distribution, and remarks. Use LIKE for queries.
		- Type: General location information.
		- Remarks: Location information about cultivation or native area.
		- Distribution: Locations where the plant is common. May contain multiple locations, use LIKE for queries.
		10. **Groups**: Contains either "Gymnosperms" or "Angiosperms".
		11. **Urban**: Contains either "YES" or "NO". Specifies whether the plant is urban.
		12. **Fruit**: Contains either "YES" or "NO". Specifies whether the plant is a fruit plant.
		13. **Medicinal**: Contains either "YES" or "NO". Specifies whether the plant is medicinal.
		14. **Genus_Number**: Contains the Genus Number of the plant.
		15. **Accepted_name_number**: Contains the Accepted Name Number of the plant.

		Below are examples of questions and their corresponding SQL queries.
		"""



		agent_prompt = PromptTemplate.from_template("User input: {input}\nSQL Query: {query}")
		agent_prompt_obj = FewShotPromptTemplate(
				example_selector=example_selector,
				example_prompt=agent_prompt,
				prefix=prefix_prompt,
				suffix="",
				input_variables=["input"],
		)

		full_prompt = ChatPromptTemplate.from_messages(
				[
						SystemMessagePromptTemplate(prompt=agent_prompt_obj),
						("human", "{input}"),
						MessagesPlaceholder("agent_scratchpad"),
				]
		)
		return full_prompt

def initalize_sql_agent(llm, db):

		dynamic_few_shot_prompt = get_dynamic_prompt_template()

		agent = create_sql_agent(llm, db=db, prompt=dynamic_few_shot_prompt, agent_type="openai-tools", verbose=True)

		return agent

def generate_response_agent(agent,user_question):
	response = agent.invoke({"input": user_question})
	return response