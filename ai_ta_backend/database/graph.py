import os
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph
from langchain_openai import ChatOpenAI

class GraphDatabase:
    def __init__(self):
        self.graph = Neo4jGraph(
            url=os.environ['NEO4J_URI'],
            username=os.environ['NEO4J_USERNAME'],
            password=os.environ['NEO4J_PASSWORD'],
            database=os.environ['NEO4J_DATABASE'],
            refresh_schema=False,
            #enhanced_schema=True,
        )

        self.chain = GraphCypherQAChain.from_llm(
            ChatOpenAI(temperature=0),
            graph=self.graph,
            verbose=False,
            allow_dangerous_requests=True,
        )
        
