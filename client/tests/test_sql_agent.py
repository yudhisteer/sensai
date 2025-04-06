import os

import instructor
import sqlparse
from openai import OpenAI
from pydantic import BaseModel, field_validator

from client.agents.common.base import Agent, AgentConfig
from client.agents.common.runner import AppRunner
from client.agents.common.utils import pretty_print_messages
from client.common.utils import pretty_print_pydantic_model


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

# configure the runner
config_dict = {
    "max_interactions": 3,
    "token_limit": 1000,
    "api_key": os.getenv("OPENAI_API_KEY"),
}
config = AgentConfig(config_dict)

# initialize the runner
runner = AppRunner(config)



# ------------------------------------------------------------------
# Data Model
# ------------------------------------------------------------------

class SQLQueryModel(BaseModel):
    query: str

    @field_validator("query")
    def validate_sql_query(cls, value: str) -> str:
        # Remove leading/trailing whitespace
        value = value.strip()

        # Basic check: ensure query isn't empty
        if not value:
            raise ValueError("SQL query cannot be empty")

        # Use sqlparse to check if the query is syntactically valid
        try:
            parsed = sqlparse.parse(value)
            if not parsed:
                raise ValueError("Invalid SQL query: unable to parse")

            # Optional: Check for specific keywords you want to disallow
            query_upper = value.upper()
            forbidden_keywords = ["DROP", "DELETE", "TRUNCATE"]
            for keyword in forbidden_keywords:
                if keyword in query_upper:
                    raise ValueError(f"SQL query contains forbidden keyword: {keyword}")

        except Exception as e:
            raise ValueError(f"Invalid SQL query: {str(e)}")

        return value


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


# ------------------------------------------------------------------
# SQL Agent
# ------------------------------------------------------------------

sql_agent = Agent(
    name="sql_agent",
    instructions=sql_system_prompt, # inject data (table_schema) in the system prompt
    response_model=SQLQueryModel,
    functions=[],
)


if __name__ == "__main__":

    query = "What is the average temperature last month?"

    # Run the sql agent
    response = runner.run(
        agent=sql_agent,
        query=query,
        context_variables=table_schema, # because instructions is a function that takes context_variables as an argument
    )
    pretty_print_pydantic_model(response)
    pretty_print_messages(response.messages)
    print("-" * 100)
