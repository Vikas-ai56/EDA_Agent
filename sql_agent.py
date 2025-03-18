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
            return {"results": "NOT_RELEVANT"}

        try:
            results = self.db_manager.execute_query(query)
            return {"results": results}
        except Exception as e:
            return {"error": str(e)}

    # else block within the try block is complete for now

    def validator(self, state: dict) -> dict:
        """Validate the generated SQL query."""
        sql_query = state['sql_query']

        if sql_query == "NOT_RELEVANT":
            return {"sql_valid": False, "sql_issues": "NOT_RELEVANT", "valid": "invalid"}

        try:
            ret, executable = self.db_manager.validate_query(sql_query)
            if executable:
                return {"sql_valid": True, "valid": "valid"}
            else:
                return {"sql_valid": False, "sql_issues": ret, "valid": "invalid"}
        except Exception as e:
            print(f"Error during SQL validation: {e}")
            return {"sql_valid": False, "sql_issues": str(e), "valid": "invalid"}


    def fix_sql(self, query:str, error_message:str)-> str | None:
        """
        Attempts to fix an invalid SQL query using the LLM.
        Has a maximum of 3 retries in order to avoid a recursive loop and reduce cost.

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

    def format_results(self, state: dict) -> dict:
        """Format query results into a human-readable response."""
        question = state['question']
        results = state['results']

        if results == "NOT_RELEVANT":
            return {"answer": "Sorry, I can only give answers relevant to the database."}

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an AI assistant that formats database query results into a human-readable response. Give a conclusion to the user's question based on the query results. Do not give the answer in markdown format. Only give the answer in one line."),
            ("human", "User question: {question}\n\nQuery results: {results}\n\nFormatted response:"),
        ])

        response = self.llm_manager.invoke(prompt, question=question, results=results)
        return {"answer": response}
    
    def choose_visualization(self, state: dict) -> dict:
        """Choose an appropriate visualization for the data."""
        question = state['question']
        results = state['results']
        sql_query = state['sql_query']

        if results == "NOT_RELEVANT":
            return {"visualization": "none", "visualization_reasoning": "No visualization needed for irrelevant questions."}

        prompt = ChatPromptTemplate.from_messages([
            ("system", '''
            You are an AI assistant that recommends appropriate data visualizations. Based on the user's question, SQL query, and query results, suggest the most suitable type of graph or chart to visualize the data. If no visualization is appropriate, indicate that.

            Available chart types and their use cases:
            - Bar Graphs: Best for comparing categorical data or showing changes over time when categories are discrete and the number of categories is more than 2. Use for questions like "What are the sales figures for each product?" or "How does the population of cities compare? or "What percentage of each city is male?"
            - Horizontal Bar Graphs: Best for comparing categorical data or showing changes over time when the number of categories is small or the disparity between categories is large. Use for questions like "Show the revenue of A and B?" or "How does the population of 2 cities compare?" or "How many men and women got promoted?" or "What percentage of men and what percentage of women got promoted?" when the disparity between categories is large.
            - Scatter Plots: Useful for identifying relationships or correlations between two numerical variables or plotting distributions of data. Best used when both x axis and y axis are continuous. Use for questions like "Plot a distribution of the fares (where the x axis is the fare and the y axis is the count of people who paid that fare)" or "Is there a relationship between advertising spend and sales?" or "How do height and weight correlate in the dataset? Do not use it for questions that do not have a continuous x axis."
            - Pie Charts: Ideal for showing proportions or percentages within a whole. Use for questions like "What is the market share distribution among different companies?" or "What percentage of the total revenue comes from each product?"
            - Line Graphs: Best for showing trends and distributionsover time. Best used when both x axis and y axis are continuous. Used for questions like "How have website visits changed over the year?" or "What is the trend in temperature over the past decade?". Do not use it for questions that do not have a continuous x axis or a time based x axis.

            Consider these types of questions when recommending a visualization:
            1. Aggregations and Summarizations (e.g., "What is the average revenue by month?" - Line Graph)
            2. Comparisons (e.g., "Compare the sales figures of Product A and Product B over the last year." - Line or Column Graph)
            3. Plotting Distributions (e.g., "Plot a distribution of the age of users" - Scatter Plot)
            4. Trends Over Time (e.g., "What is the trend in the number of active users over the past year?" - Line Graph)
            5. Proportions (e.g., "What is the market share of the products?" - Pie Chart)
            6. Correlations (e.g., "Is there a correlation between marketing spend and revenue?" - Scatter Plot)

            Provide your response in the following format:
            Recommended Visualization: [Chart type or "None"]. ONLY use the following names: bar, horizontal_bar, line, pie, scatter, none
            Reason: [Brief explanation for your recommendation]
            '''),
                        ("human", '''
            User question: {question}
            SQL query: {sql_query}
            Query results: {results}

            Recommend a visualization:'''),
                    ])

        response = self.llm_manager.invoke(prompt, question=question, sql_query=sql_query, results=results)
        
        lines = response.split('\n')
        visualization = lines[0].split(': ')[1]
        reason = lines[1].split(': ')[1]

        return {"visualization": visualization, "visualization_reason": reason}