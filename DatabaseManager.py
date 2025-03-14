# Note the execute query function is used to perform data retrieval option and not INSERT , DELETE or UPDATE operations

# Alternative setup of the self.Session object
"""
def session(engine):
    session = sessionmaker(bind=engine)()
    if engine.dialect.name == "sqlite":
        session.execute(text('SELECT InitSpatialMetaData()'))
    yield session
    session.rollback()
"""

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import  declarative_base , Session
from sqlalchemy import text
from State import column , foreign_relation
import networkx as nx

class DatabaseManager:
    # -----------------------------------------------------------------------------------------------------------------------------
    # Setup SQLAlchemy
    # -----------------------------------------------------------------------------------------------------------------------------

    def __init__(self, db_url="sqlite:///chinook.db"):
        self.db_url = db_url
        self.graph = None
        try:
            self.engine = create_engine(self.db_url,echo=True)
            self.Session = Session(bind=self.engine)
            self.Base = declarative_base()
            self.inspector = inspect(self.engine)
            self.graph = nx.DiGraph()
        except Exception as e:
            raise Exception(f"Error connecting to database: {e}")
        
    def get_db_type(self):
        return self.engine.dialect.name
    
    def get_schema(self):
        """
        Extracts the database schema, including table names, column names,
        data types, primary keys, and foreign keys.

        Returns:
            dict: A dictionary representing the database schema.  The keys are
                  table names, and the values are dictionaries containing
                  column information and foreign key relationships.
        """
        schema = {}

        for table_name in self.inspector.get_table_names():
            schema[table_name] = {
                'columns': [],
                'primary_key': self.inspector.get_pk_constraint(table_name),
                'foreign_keys': []
            }

        # Stores the details of the columns in the table (Basically Summary of the column)

            for columns in self.inspector.get_columns(table_name):
                schema[table_name]['columns'].append(column(name = columns['name'],
                                                             type = str(columns['type']),
                                                             nullable = columns['nullable'],
                                                             default = columns['default']))
                

        # Stores the foreign key relationships for the table with other tables
            
            for fk in self.inspector.get_foreign_keys(table_name):
                schema[table_name]['foreign_keys'].append(foreign_relation(constrained_column = fk['constrained_columns'],
                                                                          referenced_table = fk['referred_table'],
                                                                          referenced_column = fk['referred_columns']))

        return {'schema':schema}

    # -----------------------------------------------------------------------------------------------------------------------------
    # Setup graph and extract the relationships between tables 
    # The graph is a directed graph which allows the llm to understand the relationships between tables better
    # -----------------------------------------------------------------------------------------------------------------------------

    def get_schema_graph(self):
        graph = nx.DiGraph()
        schema_dict = self.get_schema() 
        schema_dict = schema_dict['schema']

        for table_name, table_data in schema_dict.items():
            graph.add_node(table_name, type="table", **table_data)

            # Add column nodes and edges
            for col in table_data["columns"]:
                column_name = f"{table_name}.{col.name}"  # Use dictionary access
                graph.add_node(column_name, **col.dict()) 
                graph.add_edge(table_name, column_name, relationship="has_column")
            # Add foreign key edges
            for fk in table_data["foreign_keys"]:
                graph.add_edge(table_name, fk.referenced_table, relationship="foreign_key",
                                constrained_columns=fk.constrained_column,  # Store as list
                                referred_columns=fk.referenced_column) 
        return graph

    def validate_query(self,query):
        try:
            with self.Session as session:
                session.execute(text(query))
                session.commit()
                print("Query is valid")
                return "Query is valid", True
            
        except Exception as e:
            session.rollback()
            return str(e) , False
    

    def execute_query(self,query):
        try:
            with self.Session as session: # creating a Session instance
                result = session.execute(text(query))
                
                if result.returns_rows:
                    columns = result.keys()
                    rows = result.fetchall()
                    data = [dict(zip(columns, row)) for row in rows]
                    session.commit()
                    return data
        
        except Exception as e:
            return {'error': str(e)}

