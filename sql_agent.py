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

        response = self.llm_manager.invoke(prompt, ParsedQuestion , schema=schema, question=question)
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

        schema = db_manager.get_schema() # No need for UUID with local DB

        prompt = ChatPromptTemplate.from_messages([
            ("system", '''You are an AI assistant that generates SQL queries based on user questions,
            database schema, and unique nouns found in the relevant tables. Generate a valid SQL
            query to answer the user's question.

    If there is not enough information to write a SQL query, respond with "NOT_ENOUGH_INFO".

    Here are some examples:

    1. What is the top selling product?
    Answer: SELECT product_name, SUM(quantity) as total_quantity FROM sales WHERE product_name
    IS NOT NULL AND quantity IS NOT NULL AND product_name != "" AND quantity != "" AND
    product_name != "N/A" AND quantity != "N/A" GROUP BY product_name ORDER BY total_quantity DESC
    LIMIT 1

    2. What is the total revenue for each product?
    Answer: SELECT `product name`, SUM(quantity * price) as total_revenue FROM sales WHERE
    `product name` IS NOT NULL AND quantity IS NOT NULL AND price IS NOT NULL AND `product name`
    != "" AND quantity != "" AND price != "" AND `product name` != "N/A" AND quantity != "N/A" AND
    price != "N/A" GROUP BY `product name`  ORDER BY total_revenue DESC

    3. What is the market share of each product?
    Answer: SELECT `product name`, SUM(quantity) * 100.0 / (SELECT SUM(quantity) FROM sales)
    as market_share FROM sales WHERE `product name` IS NOT NULL AND quantity IS NOT NULL AND
    `product name` != "" AND quantity != "" AND `product name` != "N/A" AND quantity != "N/A"
    GROUP BY `product name`  ORDER BY market_share DESC

    4. Plot the distribution of income over time
    Answer: SELECT income, COUNT(*) as count FROM users WHERE income IS NOT NULL AND income != ""
    AND income != "N/A" GROUP BY income

    THE RESULTS SHOULD ONLY BE IN THE FOLLOWING FORMAT, SO MAKE SURE TO ONLY GIVE TWO OR THREE COLUMNS:
    [[x, y]]
    or
    [[label, x, y]]

    For questions like "plot a distribution of the fares for men and women", count the frequency
    of each fare and plot it. The x axis should be the fare and the y axis should be the count
    of people who paid that fare.
    SKIP ALL ROWS WHERE ANY COLUMN IS NULL or "N/A" or "".
    Just give the query string. Do not format it. Make sure to use the correct spellings of nouns
    as provided in unique nouns list. All the table and column names should be enclosed in backticks.
    '''),
            ("human", ''' Before generating the SQL query, understand the type of sql databse i.e. whether it is a **SQLlite, MySQL, PostgreSQL, MariaDB etc** type of database and then generate query accordingly to that type of database.
    ===Database schema:
    {schema}

    ===User question:
    {question}

    ===Relevant tables and columns:
    {parsed_question}

    ===Unique nouns in relevant tables:
    {unique_nouns}

    Generate SQL query string'''),
        ])

        try:
            response = llm_manager.invoke(prompt, parser=None , schema=schema, question=question, parsed_question=parsed_question, unique_nouns=unique_nouns)

            if response.strip() == "NOT_ENOUGH_INFO":
                return {"sql_query": "NOT_RELEVANT"}
            else:
                return {"sql_query": response}
            
        except Exception as e:
            print(f"Error during LLM invocation: {e}")  # Log the error
            return {"sql_query": "ERROR"} # Or some other error indicator