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

def initialize_agent():
    load_dotenv()

    # Set up the Database
    db = SQLDatabase.from_uri("sqlite:///plants_of_India_demo.db")

    # Define the system prefixes and examples
    system_prefix_asmita = """Given the following user question, corresponding SQL query, and SQL result, answer the user question.
   Return the SQL query and SQL result along with the final answer.
    Limit your search to the "Plants" table.
    Restrict to data found in the "plants" table only. If the SQL result is empty, mention that the query returned 0 rows. Do not come up with answers from your own knowledge.
    If the SQL result is empty, mention that the query returned 0 rows.
    Any SQL queries related to string comparison like location, author name, etc. should use LIKE statement.
    Refer to the description below to obtain additional information about the columns.
    Column Description:
    1. recordType: This column contains text codes which indicate what information is present in the current row about the plant.
    FA = Family Name, Genus Name, Sciecific Name.
    TY = Type
    GE = Genus Name
    AN = Family Name (contains Accepted Name), Genus Name, Scientific Name, Author Name, Publication, Volume:Page, and Year of Publication
    HB = Habit
    DB = Distribution or location of the plant
    RE = Remarks
    SN = Family Name (contains Synonym), Genus Name, Sciecific Name, Author Name, Publication, Volume:Page, and Year of Publication

    2. familyName: This columns contains the Family Name of the plant. A family is made of several genera and genus is made of several species (scientific names).
    3. genusName: This columns contains the Genus Name of the plant.
    4. scientificName: This columns contains the Scientific Name of the plant species.
    5. publication: Name of the journal or book where the plant discovery information is published. Use LIKE statement when creating SQL queries related to publication name.
    6. volumePage: The volume and page number of the publication containing the plant information.
    7. yearOfpublication: The year in which the plant discovery information was published or the year the plant was found / discovered.
    8. author: This column may contain multiple authors separated by &. When creating SQL queries related to authors or names, always use a LIKE statement.
    9. additionalDetail2: This column contains 4 types of information - type, habit, distribution and remarks. Use LIKE statement when creating SQL queries related to any of the three fields of additional details.
      - Type mentions information about location.
      - Remarks mentions location information about where the plant is cultivated or native to.
      - Distribution mentions the locations where the plant is distributed. It may contain multiple locations, so always use a LIKE statement when creating SQL queries related to distribution or plant location.

    10. groups: This column contains one of the two values - Gymnosperms and Angiosperms.
    11. familyNumber: This column contains a number which is assigned to the family.
    12. genusNumber: This coulumn contains a number which is assigned to a genus within a family.
    13. acceptedNameNumber: This coulumn contains a number which is assigned to a accepted name of a genus within a family
    14. synonymNumber: This coulumn contains a number which is assigned to a synonym name associated with a an accepted name of a genus within a family
DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.

If the question does not seem related to the database, just return "I don't know" as the answer.

Here are some examples of user inputs and their corresponding SQL queries:
"""


    examples = [    
    {"input": "List all the accepted names under the family 'Gnetaceae'.", 
     "query": """
SELECT DISTINCT scientificName FROM plants
JOIN (
    SELECT familyNumber, genusNumber, acceptedNameNumber
    FROM plants
    WHERE familyNumber IN (
        SELECT DISTINCT familyNumber FROM plants WHERE familyName = 'Gnetaceae'
    )
) b
ON plants.genusNumber = b.genusNumber AND plants.acceptedNameNumber = b.acceptedNameNumber AND plants.familyNumber = b.familyNumber
WHERE plants.recordType = 'AN';
"""},
    {
        "input": "List all the accepted species that are introduced.",
        "query": """
SELECT DISTINCT scientificName FROM plants
JOIN (
    SELECT familyNumber, genusNumber, acceptedNameNumber
    FROM plants
    WHERE recordType = 'RE'and additionalDetail2 LIKE '%cultivated%'

) b
ON plants.genusNumber = b.genusNumber AND plants.acceptedNameNumber = b.acceptedNameNumber AND plants.familyNumber = b.familyNumber
WHERE plants.recordType = 'AN';
""",
    },
    {
        "input": "List all the accepted names with type 'Cycad'",
        "query": """
SELECT DISTINCT scientificName FROM plants
JOIN (
    SELECT familyNumber, genusNumber, acceptedNameNumber
    FROM plants
    WHERE recordType = 'HB'and additionalDetail2 LIKE '%Cycad%'

) b
ON plants.genusNumber = b.genusNumber AND plants.acceptedNameNumber = b.acceptedNameNumber AND plants.familyNumber = b.familyNumber
WHERE plants.recordType = 'AN';
""",
    },
    {
        "input": "List all the accepted names under the genus 'Cycas' with more than two synonyms.",
        "query": """
SELECT DISTINCT scientificName FROM plants
JOIN (
    SELECT familyNumber, genusNumber, acceptedNameNumber
    FROM plants
    WHERE genusNumber IN (
        SELECT DISTINCT genusNumber FROM plants WHERE GenusName = 'Cycas'
    )
    AND familyNumber IN (
        SELECT DISTINCT familyNumber FROM plants WHERE GenusName = 'Cycas'
    )
    AND synonymNumber > 2
) b
ON plants.genusNumber = b.genusNumber AND plants.acceptedNameNumber = b.acceptedNameNumber AND plants.familyNumber = b.familyNumber
WHERE plants.recordType = 'AN';
""",
    },
 {
        "input":'List all the accepted names published in Asian J. Conservation Biol.',
        "query": """
    SELECT DISTINCT scientificName
    FROM plants
    WHERE recordType = 'AN' AND publication LIKE '%Asian J. Conservation Biol%';

""",
    },
 {
        "input": 'List all the accepted names linked with endemic tag.',
        "query": """
SELECT DISTINCT scientificName FROM plants
JOIN (
    SELECT familyNumber, genusNumber, acceptedNameNumber
    FROM plants
    WHERE recordType = 'DB'and additionalDetail2 LIKE '%Endemic%'

) b
ON plants.genusNumber = b.genusNumber AND plants.acceptedNameNumber = b.acceptedNameNumber AND plants.familyNumber = b.familyNumber
WHERE plants.recordType = 'AN';
""",
    },
 {
        "input": 'List all the accepted names that have no synonyms.' ,
        "query": """
SELECT  DISTINCT a.scientificName FROM plants a
group by a.familyNumber,a.genusNumber,a.acceptedNameNumber
HAVING  SUM(a.synonymNumber) = 0 AND a.acceptedNameNumber > 0;
""",
    },
 {
        "input": 'List all the accepted names authored by Roxb.',
        "query": """
SELECT scientificName 
FROM plants
WHERE recordType = 'AN'and actualAuthorName LIKE '%Roxb%';
""",
    },
 {
        "input": 'List all genera within each family',
        "query": """
SELECT familyName, genusName 
FROM plants
WHERE recordType = 'GE';
""",
    },
 {
        "input": 'Did Minq. discovered Cycas ryumphii?',
        "query": """SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1
            FROM plants as a
            WHERE a.scientificName = 'Cycas rumphii'
            AND a.author = 'Miq.'
        ) THEN 'TRUE'
        ELSE 'FALSE'
    END AS ExistsCheck;
""",
    },
]

    # Define the prompt template
    example_prompt = PromptTemplate.from_template("User input: {input}\nSQL query: {query}")
    prompt = FewShotPromptTemplate(
        examples=examples[:5],
        example_prompt=example_prompt,
        prefix=system_prefix_asmita,
        suffix="",
        input_variables=["input", "top_k", "table_info"],
    )

    # Define the full prompt structure
    full_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate(prompt=prompt),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    # Initialize the OpenAI models
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0)

    # Create the SQL agent
    agent = create_sql_agent(
        llm=llm,
        db=db,
        prompt=full_prompt,
        verbose=True,
        agent_type="openai-tools",
    )

    return agent

def generate_response(user_input):
    agent = initialize_agent()
    output = agent.invoke(user_input)
    return output
