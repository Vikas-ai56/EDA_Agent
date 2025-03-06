# Note the execute query function is used to perform data retrieval option and not INSERT , DELETE or UPDATE operations

#-----------------------------------------------------------------------------------------------------------------------------
# Setup SQLAlchemy
#-----------------------------------------------------------------------------------------------------------------------------

from sqlalchemy import create_engine, inspect 
from sqlalchemy.orm import  Session , declarative_base 
from sqlalchemy import text
from State import column , foreign_relation

class DatabaseManager:
    def __init__(self, db_url = "sqlite:///chinook.db"):
        self.db_url = db_url
        self.engine = create_engine(self.db_url)
        self.Session = Session(bind=self.engine)
        self.Base = declarative_base()
        self.inspector = inspect(self.engine)
    
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
    
    def execute_query(self,query):
        try:   
            with self.Session as session:
                result = session.execute(text(query))
                
                if result.returns_rows:
                    columns = result.keys()
                    rows = result.fetchall()
                    data = [dict(zip(columns, row)) for row in rows]
                    session.commit()
                    return {'answer': data}
        
        except Exception as e:
            return {'error': str(e)}


