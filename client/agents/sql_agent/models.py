from pydantic import Field

from client.agents.common.tools import ResponseBase


class SQLResponse(ResponseBase):
    is_sql_query: bool = Field(description="Whether the response is a SQL query")
    sql_query: str = Field(description="The SQL query to execute")
