# EDA Agent 

This repository contains a prototype of a basic workflow system that generates and validates SQL queries, formats results, and recommends visualizations. Please note that the code may have bugs or incomplete functionalities.

---

## 1. Project Setup

### Python Environment
1. Install Python 3.10+ (or higher).
2. Create and activate a virtual environment:
   - **Windows**  
     ```
     python -m venv .venv
     .venv\Scripts\activate
     ```
   - **macOS/Linux**  
     ```
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. Install project dependencies:
   ```
   pip install -r requirements.txt
   ```

### Environment Variables
1. Copy `.env.example` to `.env` and fill in the required values (for example, OpenAI API key).

```
OPENAI_API_KEY="YOUR_API_KEY_HERE"
```

Make sure your `.env` file is not tracked by version control by checking the `.gitignore` file.

---

## 2. Project Structure

```
ML
 └── EDA_agent
     ├── .env.example
     ├── .gitignore
     ├── requirements.txt
     ├── DatabaseManager.py
     ├── DataFormatter.py
     ├── LLMManager.py
     ├── State.py
     ├── sql_agent.py
     ├── workflow_manager.py
     ├── graph_instructions.py
     ├── prompt_templates.py
     ├── sqlalchemy.md
     └── ...
```

---

## 3. Files and Important Functions

### DatabaseManager.py
- **DatabaseManager**  
  Manages database connections and sessions using SQLAlchemy.  
  - `get_schema()` – Retrieves database tables, columns, primary keys, and foreign keys.  
  - `get_schema_graph()` – Builds a directed graph (NetworkX) of tables and their relationships.  
  - `validate_query(query)` – Checks if an SQL query can be executed without errors.  
  - `execute_query(query)` – Executes a read-only SQL query and returns data rows.

### DataFormatter.py
- **DataFormatter**  
  Formats raw SQL query results into different data structures suitable for visualization.  
  - `format_data_for_visualization(state)` – Main entry for formatting data based on the chosen visualization.  
  - `_format_line_data()`, `_format_bar_data()`, `_format_scatter_data()` – Helper functions for specific visual formats.

### LLMManager.py
- **LLMManager**  
  A wrapper around the language model to format and execute prompts.  
  - `invoke(prompt, parser=None, **kwargs)` – Sends a prompt to the model and returns the response.

### State.py
- Defines Pydantic models used to strongly type states and data structures across the project.  
  - `column`, `foreign_relation`, `Table` – Models describing database schema.  
  - `InputState`, `OutputState` – Models for input and output data in the workflow.

### sql_agent.py
- **SQLAgent**  
  Contains methods to parse a question, generate SQL, validate queries, fix invalid SQL, and format final answers.  
  - `parse_question(state)` – Identifies relevant tables and columns.  
  - `generate_sql(...)` – Uses the language model to produce an SQL query.  
  - `validator(state)` – Validates SQL and returns status.  
  - `fix_sql(query, error_message)` – Attempts to auto-correct an invalid SQL query.

### workflow_manager.py
- **WorkflowManager**  
  Uses LangGraph to build a directed state machine for the entire question-to-answer process.  
  - `create_workflow()` – Creates the workflow graph and defines nodes and edges.  
  - `returnGraph()` – Compiles the workflow.  
  - `run_sql_agent(question, uuid)` – Runs the full workflow from question parsing to data formatting.

### graph_instructions.py
- Holds strings describing the desired data format for various chart types (e.g., bar graphs, scatter plots, and so on).

### prompt_templates.py
- Defines reusable prompt templates for generating SQL queries against different SQL dialects (SQLite, MySQL, PostgreSQL).

---

## 4. Prototype Disclaimer
This is a prototype and may contain errors or incomplete functionalities. Use at your own discretion.
