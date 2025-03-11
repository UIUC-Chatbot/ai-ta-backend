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
        )
        
        # Get schema information for the system prompt
        self.schema_info = self._get_schema_info()
        
        # Create the chain with the clinical KG system prompt
        self.chain = self._create_clinical_kg_chain()
    
    def _get_schema_info(self):
        """Extract schema information from the Neo4j database."""
        try:
            # This will get the schema without refreshing it (faster)
            return self.graph.schema
        except:
            # If schema isn't available yet, return a placeholder
            return "Schema information not available. Please refresh schema first."
    
    def _create_clinical_kg_chain(self):
        """Create a GraphCypherQAChain with a clinical KG system prompt."""
        # system_prompt = f"""
        # You are a clinical knowledge graph expert assistant that helps healthcare professionals query a medical knowledge graph.
        
        # SCHEMA INFORMATION:
        # {self.schema_info}
        
        # GUIDELINES FOR GENERATING CYPHER QUERIES:
        # 1. Always use the correct node labels and relationship types from the schema above
        # 2. For clinical entities, prefer to use specific node types like Disease, Drug, Symptom, etc.
        # 3. When searching for treatments, use relationships like TREATS, PRESCRIBED_FOR, etc.
        # 4. For finding side effects, use relationships like CAUSES, HAS_SIDE_EFFECT, etc.
        # 5. When querying for interactions, look for INTERACTS_WITH relationships
        # 6. Limit results to a reasonable number (e.g., LIMIT 10) for readability
        # 7. Include relevant properties in the RETURN clause
        # 8. Use appropriate WHERE clauses to filter results
        # 9. For text matching, use case-insensitive matching with toLower() or CONTAINS
        # 10. For complex queries, consider using multiple MATCH clauses
        
        # RESPONSE FORMAT:
        # 1. First, explain the Cypher query you're generating and why
        # 2. Present the results in a clear, structured format
        # 3. Provide a clinical interpretation of the results
        # 4. If relevant, suggest follow-up queries the user might be interested in
        
        # Remember that you're helping healthcare professionals, so be precise and clinically accurate.
        # """
        schema_info = self.schema_info
        system_prompt = f"""
        You are a clinical knowledge graph expert assistant that helps healthcare professionals query a medical knowledge graph.
        
        SCHEMA INFORMATION:
        {schema_info}
        
        COMMON NODE TYPES IN THIS KNOWLEDGE GRAPH:
        - Disease: Represents medical conditions and disorders
        - Drug: Represents pharmaceutical compounds and medications
        - Symptom: Represents clinical manifestations of diseases
        - Gene: Represents genetic entities related to diseases
        - Protein: Represents proteins that may be targets for drugs
        - Pathway: Represents biological pathways involved in disease mechanisms
        - Food: Represents food items and their nutritional properties
        
        
        COMMON RELATIONSHIP TYPES:
        - TREATS: Connects drugs to diseases they treat
        - CAUSES: Connects entities to effects they produce
        - HAS_SYMPTOM: Connects diseases to their symptoms
        - INTERACTS_WITH: Connects drugs that have interactions
        - EXPRESSED_IN: Connects genes/proteins to anatomical locations
        - PART_OF: Connects entities to larger systems they belong to
        - ASSOCIATED_WITH: General association between entities
        - FOUND_IN: Connects functional region to proteins
        - BELONGS_TO_PROTEIN: Connects proteins to peptides
        
        GUIDELINES FOR GENERATING CYPHER QUERIES:
        1. Always use the correct node labels and relationship types from the schema
        2. For clinical entities, use the most specific node type available
        3. Use appropriate WHERE clauses with case-insensitive matching:
        - For exact matches: WHERE toLower(n.name) = toLower("term")
        - For partial matches: WHERE toLower(n.name) CONTAINS toLower("term")
        4. For complex queries, use multiple MATCH clauses rather than long path patterns
        5. Include LIMIT clauses (typically 5-15 results) for readability
        6. For property access, use the correct property names from the schema
        7. When appropriate, use aggregation functions (count, collect, etc.)
        8. For path finding, consider using shortest path algorithms
        9. Return the most clinically relevant properties in the RETURN clause
        10. For temporal queries, use appropriate date/time functions
        
        RESPONSE FORMAT:
        1. First, explain the Cypher query you're generating and why it addresses the user's question
        2. Present the results in a clear, structured format (tables or lists)
        3. Provide a clinical interpretation of the results, highlighting key findings
        4. If relevant, suggest follow-up queries the user might be interested in
        5. If the results are empty, suggest modifications to the query that might yield results
        
        CLINICAL ACCURACY:
        1. Ensure all medical information is evidence-based and accurate
        2. Clearly distinguish between established medical facts and exploratory findings
        3. Use precise medical terminology appropriate for healthcare professionals
        4. Acknowledge limitations in the data or knowledge graph when relevant
        
        Remember that you're helping healthcare professionals make clinical decisions, so accuracy and precision are paramount.
        """
        print("SYSTEM PROMPT: ", system_prompt)
        return GraphCypherQAChain.from_llm(
            ChatOpenAI(temperature=0, model="gpt-4o"),
            graph=self.graph,
            verbose=False,
            allow_dangerous_requests=True,
            system_message=system_prompt,
        )
    
    def create_chain_with_custom_prompt(self, additional_instructions=""):
        """
        Create a new chain with a custom prompt that includes additional instructions.
        
        Args:
            additional_instructions (str): Additional instructions to add to the system prompt
            
        Returns:
            GraphCypherQAChain: A new chain with the custom prompt
        """
        system_prompt = f"""
        You are a clinical knowledge graph expert assistant that helps healthcare professionals query a medical knowledge graph.
        
        SCHEMA INFORMATION:
        {self.schema_info}
        
        GUIDELINES FOR GENERATING CYPHER QUERIES:
        1. Always use the correct node labels and relationship types from the schema above
        2. For clinical entities, prefer to use specific node types like Disease, Drug, Symptom, etc.
        3. When searching for treatments, use relationships like TREATS, PRESCRIBED_FOR, etc.
        4. For finding side effects, use relationships like CAUSES, HAS_SIDE_EFFECT, etc.
        5. When querying for interactions, look for INTERACTS_WITH relationships
        6. Limit results to a reasonable number (e.g., LIMIT 10) for readability
        7. Include relevant properties in the RETURN clause
        8. Use appropriate WHERE clauses to filter results
        9. For text matching, use case-insensitive matching with toLower() or CONTAINS
        10. For complex queries, consider using multiple MATCH clauses
        
        RESPONSE FORMAT:
        1. First, explain the Cypher query you're generating and why
        2. Present the results in a clear, structured format
        3. Provide a clinical interpretation of the results
        4. If relevant, suggest follow-up queries the user might be interested in
        
        Remember that you're helping healthcare professionals, so be precise and clinically accurate.
        
        ADDITIONAL INSTRUCTIONS:
        {additional_instructions}
        """
        print("SYSTEM PROMPT: ", system_prompt)
        
        return GraphCypherQAChain.from_llm(
            ChatOpenAI(temperature=0, model="gpt-4o"),
            graph=self.graph,
            verbose=False,
            allow_dangerous_requests=True,
            system_message=system_prompt,
        )
    
    def refresh_schema(self):
        """Refresh the schema and update the chain with the new schema information."""
        self.graph.refresh_schema()
        self.schema_info = self._get_schema_info()
        self.chain = self._create_clinical_kg_chain()
        return "Schema refreshed successfully"
        
