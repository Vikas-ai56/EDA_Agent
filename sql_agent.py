from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from DatabaseManager import DatabaseManager
from LLMManager import LLMManager
from State import InputState , ParsedQuestion
from pydantic import BaseModel , Field

# -----------------------------------------------------------------------------------------------------------------------------
# Defining the schema for the parsed question
# -----------------------------------------------------------------------------------------------------------------------------

# Check State.py for the definition of ParsedQuestion

# -----------------------------------------------------------------------------------------------------------------------------
# Building the SQL Agent class
# -----------------------------------------------------------------------------------------------------------------------------

class SQLAgent:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.llm_manager = LLMManager()

    def parse_question(self, state:InputState):
        question = state['question']
        schema = state['schema']

        prompt = ChatPromptTemplate.from_messages([
            ("system", '''You are a data analyst that can help summarize SQL tables and parse user questions about a database. 
                          Given the question and database schema, identify the relevant tables and columns. 
                          If the question is not relevant to the database or if there is not enough information to answer the question, set is_relevant to false.

                         The "noun_columns" field should contain only the columns that are relevant to the question and contain nouns or names,
                         for Example:-
                                     the column "Artist name" contains nouns relevant to the question "What are the top selling artists?", but the column "Artist ID" 
                                     is not relevant because it does not contain a noun. Do not include columns that contain numbers.
             '''),
             ("human", "===Database schema===\n{schema}\n\n===User question===\n{question}\n\n Now Identify relevant tables and columns:")
        ])

        response = self.llm_manager.invoke(prompt, ParsedQuestion , schema=schema, question=question)
        return {'parsed_question': response}
        
        