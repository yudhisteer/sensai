import os
import sqlparse
from pydantic import BaseModel, field_validator, Field

from client.agents.common.base import Agent, AgentConfig
from client.agents.common.runner import AppRunner
from client.agents.common.utils import pretty_print_messages
from client.agents.common.types import FuncResult
from client.common.utils import pretty_print_pydantic_model

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

config_dict = {
    "max_interactions": 3,
    "token_limit": 1000,
    "api_key": os.getenv("OPENAI_API_KEY"),
}
config = AgentConfig(config_dict)
runner = AppRunner(config)

# ------------------------------------------------------------------
# Data Models
# ------------------------------------------------------------------

class SQLQueryModel(BaseModel):
    query: str

    @field_validator("query")
    def validate_sql_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("SQL query cannot be empty")
        try:
            parsed = sqlparse.parse(value)
            if not parsed:
                raise ValueError("Invalid SQL query: unable to parse")
            query_upper = value.upper()
            forbidden_keywords = ["DROP", "DELETE", "TRUNCATE"]
            for keyword in forbidden_keywords:
                if keyword in query_upper:
                    raise ValueError(f"SQL query contains forbidden keyword: {keyword}")
        except Exception as e:
            raise ValueError(f"Invalid SQL query: {str(e)}")
        return value


class SimpleResponse(BaseModel):
    answer: str = Field(description="A simple response to the query.")

# ------------------------------------------------------------------
# Instructions
# ------------------------------------------------------------------

table_schema = {
    "table_name": "temperature_readings",
    "table_schema": """
        {
    "table_name": "temperature_readings",
    "schema": [
        {
        "column_name": "id",
        "data_type": "uuid",
        "is_nullable": "NO",
        "column_default": "uuid_generate_v4()"
        },
        {
        "column_name": "celsius",
        "data_type": "numeric",
        "is_nullable": "NO",
        "column_default": null
        },
        {
        "column_name": "fahrenheit",
        "data_type": "numeric",
        "is_nullable": "NO",
        "column_default": null
        },
        {
        "column_name": "created_at",
        "data_type": "timestamp with time zone",
        "is_nullable": "YES",
        "column_default": "now()"
        }
    ]
    }
    """,
}

def sql_system_prompt(context_variables: dict) -> str:
    table_schema = context_variables.get("table_schema", None)
    table_name = context_variables.get("table_name", None)
    return f"""You are a SQL expert. You will be provided with user queries about the table '{table_name}'.
    The table has the following schema:
    {table_schema}

    Generate SQL queries that:
    1. Strictly follow this schema
    2. Use the correct column names and data types
    3. Respect NULL/NOT NULL constraints
    4. Consider default values where applicable

    Return only the SQL query without any explanations.
    """

def triage_system_prompt(context_variables: dict) -> str:
    return """You are a triage assistant. Analyze the user query and determine its type:
    - If it’s a SQL-related question about data (e.g., averages, counts), call switch_to_sql_agent.
    - For other questions, call switch_to_fallback_agent.
    Do not answer the query yourself—route it to the appropriate agent."""


# ------------------------------------------------------------------
# Switch Functions
# ------------------------------------------------------------------

# def switch_to_sql_agent() -> FuncResult:
#     """Route the query to the SQL agent."""
#     return FuncResult(value="Routing to SQL agent", agent=sql_agent)

def switch_to_sql_agent():
    return sql_agent

# def switch_to_fallback_agent() -> FuncResult:
#     """Route the query to the fallback agent."""
#     return FuncResult(value="Routing to fallback agent", agent=fallback_agent)

def switch_to_fallback_agent():
    return fallback_agent

# ------------------------------------------------------------------
# Pre-defined Agents
# ------------------------------------------------------------------

sql_agent = Agent(
    name="sql_agent",
    instructions=sql_system_prompt,
    response_model=SQLQueryModel,
    functions=[],
)

fallback_agent = Agent(
    name="fallback_agent",
    instructions="You’re a general assistant. Provide a simple response to the query.",
    response_model=SimpleResponse,
    functions=[],
)

triage_agent = Agent(
    name="triage_agent",
    instructions=triage_system_prompt,
    functions=[switch_to_sql_agent, switch_to_fallback_agent],
)





# ------------------------------------------------------------------
# Main Execution
# ------------------------------------------------------------------

if __name__ == "__main__":
    # SQL-related query
    query_sql = "What is the average temperature last month?"
    response_sql = runner.run(
        agent=triage_agent,
        query=query_sql,
        context_variables=table_schema,
    )
    print("SQL Query Response:")
    pretty_print_messages(response_sql.messages)
    pretty_print_pydantic_model(response_sql)
    print("-" * 100)

    # Non-SQL query
    query_non_sql = "What’s the weather like today?"
    response_non_sql = runner.run(
        agent=triage_agent,
        query=query_non_sql,
        context_variables=table_schema,  # Still passed, but ignored by fallback
    )
    print("Non-SQL Query Response:")
    pretty_print_messages(response_non_sql.messages)
    pretty_print_pydantic_model(response_non_sql)
    print("-" * 100)