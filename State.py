from typing import List, Any, Annotated, Dict, Optional
from typing_extensions import TypedDict
import operator
from pydantic import BaseModel , Field

class ParsedQuestion(BaseModel):
    BaseTable: str 
    columns: list[str]
    RelatedTables: list[str] = Field(description=f'''If the required data is not present in this table but present in a referenced table, 
                                      then the referenced table name is stored here.''')
    noun_columns: list[str] 

class foreign_relation(BaseModel):
    """
    Used for representing a foreign relation of a table w.r.t another in a database.

    Attributes:
        constrained_column (list[str]): A list of column names that are constrained by the foreign key.
        referenced_table (Optional[str]): The name of the table that the foreign key references.
        referenced_column (Optional[list[str]]): A list of column names in the referenced table that the foreign key references.
    """
    constrained_column: Annotated[list[str], operator.add]
    referenced_table: Optional[str]
    referenced_column: Optional[list[str]]

class column(BaseModel):
    """
    Represents a column in a database schema.

    Attributes:
        name (str): The name of the column.
        type (str): The data type of the column.
        nullable (bool): Indicates if the column can contain null values.
        default (Any): The default value for the column.
    """
    name: str
    type: str
    nullable: bool
    default: Any

class Table(BaseModel):
    """
    A class used to represent a Table in a database schema.

    Attributes
    ----------
    primary_key : Optional[str]
        The primary key of the table, if any.
    foreign_keys : Optional[foreign_relation]
        The foreign keys of the table, if any.
    columns : List[column]
        The columns of the table.
    """
    primary_key: Optional[str]
    foreign_keys: Optional[List[foreign_relation]]
    columns: List[column]

class InputState(TypedDict):
    question: str
    parsed_question: Dict[str, Any]
    unique_nouns: List[str]
    sql_query: str
    results: List[Any]
    visualization: Annotated[str, operator.add]
    schema : Dict[str,Table]

class OutputState(TypedDict):
    schema : Dict[str,Table]
    parsed_question: Dict[str, Any]
    error: str
    unique_nouns: List[str]
    sql_query: str
    sql_valid: bool
    sql_issues: str
    results: List[Any]
    answer: Annotated[Any, operator.add]
    visualization: Annotated[str, operator.add]
    visualization_reason: Annotated[str, operator.add]
    formatted_data_for_visualization: Dict[str, Any]