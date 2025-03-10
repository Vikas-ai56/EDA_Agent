from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from DatabaseManager import DatabaseManager
from LLMManager import LLMManager
from State import InputState , ParsedQuestion
from pydantic import BaseModel , Field
from prompt_templates import sqlite_prompt_template , mysql_prompt_template , postgresql_prompt_template

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

                Your response should be in the following JSON format:
                {{
                    "is_relevant": boolean,
                    "relevant_tables": [
                        {{
                            "table_name": string,
                            "columns": [string],
                            "noun_columns": [string]
                        }}
                    ]
                }}

                The "noun_columns" field should contain only the columns that are relevant to the question and contain nouns or names, for example, the column "Artist name" contains nouns relevant to the question "What are the top selling artists?", but the column "Artist ID" is not relevant because it does not contain a noun. Do not include columns that contain numbers.
            '''),
            ("human", "===Database schema===\n{schema}\n\n===User question===\n{question}\n\nIdentify relevant tables and columns:")
        ])

        response = self.llm_manager.invoke(prompt, parser=ParsedQuestion , schema=schema, question=question)
        return {'parsed_question': response}
        
    def get_unique_nouns(self, state: dict) -> dict:
        """Find unique nouns in relevant tables and columns."""
        parsed_question = state['parsed_question']
        
        if not parsed_question.is_relevant:
            return {"unique_nouns": []}

        unique_nouns = set()
        for table_info in parsed_question.relevant_tables:
            table_name = table_info.table_name
            noun_columns = table_info.noun_columns
            
            if noun_columns:
                column_names = ', '.join(f"`{col}`" for col in noun_columns)
                query = f"SELECT DISTINCT {column_names} FROM `{table_name}`"
                try:
                    results = self.db_manager.execute_query(query)
                    print(results)
                    for row in results:
                        unique_nouns.update(str(value) for value in row if value)
                except Exception as e:
                    print(f"Error getting unique nouns for {table_name}: {e}") #log
                    # Consider whether to reraise, continue, or return partial results
        
        return {"unique_nouns": list(unique_nouns)}

    def generate_sql(self, db_manager: DatabaseManager, llm_manager: LLMManager, state: dict) -> dict:
        
        question = state['question']
        parsed_question = state['parsed_question']
        unique_nouns = state['unique_nouns']

        if not parsed_question.is_relevant:
            return {"sql_query": "NOT_RELEVANT", "is_relevant": False}

        schema = db_manager.get_schema()
        db_type = db_manager.get_db_type()

        if db_type == "sqlite":
            prompt = sqlite_prompt_template
        elif db_type == "mysql":
            prompt = mysql_prompt_template
        elif db_type == "postgresql":
            prompt = postgresql_prompt_template
        else:
            return {"sql_query": "UNSUPPORTED_DATABASE"}

        try:
            response = llm_manager.invoke(prompt, parser=None , schema=schema, question=question, parsed_question=parsed_question, unique_nouns=unique_nouns)

            if response.strip() == "NOT_ENOUGH_INFO":
                return {"sql_query": "NOT_RELEVANT"}
            else:
                return {"sql_query": response}
            
        except Exception as e:
            print(f"Error during LLM invocation: {e}")  # Log the error
            return {"sql_query": "ERROR"} # Or some other error indicator
        
    def execute_sql(self, state: dict) -> dict:
        """Execute SQL query and return results."""
        query = state['sql_query']
        
        if query == "NOT_RELEVANT":
            return {"answer": "NOT_RELEVANT"}

        try:
            results = self.db_manager.execute_query(query)
            return {"answer": results}
        except Exception as e:
            return {"error": str(e)}

    # else block within the try block is complete for now

    def validator(self, state: dict) -> dict:
        """Validate the generated SQL query."""
        sql_query = state['sql_query']

        if sql_query == "NOT_RELEVANT":
            return {"valid": False, "issues": "NOT_RELEVANT"}

        try:
            ret , executable = self.db_manager.validate_query(sql_query)
            if executable:
                return 'valid'
            else:
                state['error'] = ret
                return 'invalid'
        except Exception as e:
            print(f"Error during SQL validation: {e}")  


    def fix_sql(self, query:str, error_message:str)-> str | None:
        """
        Attempts to fix an invalid SQL query using the LLM.

        Args:
            query: The invalid SQL query.
            error_message: The error message from the validator.

        Returns:
            The fixed SQL query, or None if it couldn't be fixed.
        """
        db_type = self.db_manager.get_db_type()

        if db_type in {"sqlite","mysql","postgresql"}:
            pass
        else:
            return {"sql_query": "UNSUPPORTED_DATABASE"}  # Or raise an exception

        prompt = ChatPromptTemplate.from_messages([
        ("system", f'''You are an AI assistant that fixes SQL queries. The database type is {db_type}.
        Here is the error message:
        {error_message}
        Fix the following SQL query:
        {query}
        Only return the corrected SQL query.
        '''),
        ])

        try:
            retries = 0

            while retries < 3:
                response = self.llm_manager.invoke(prompt,parser=None, query=query, error_message=error_message)
                # Re-validate the fixed query
                _, validation_result = self.db_manager.validate_query(response)
                if validation_result:
                    return {'sql_query':response}
                else:
                    retries += 1
            return 'Cannot write a query that is valid for your prompt'

        except Exception as e:
            print(f"Error during LLM-based SQL fixing: {e}")
            return None           

