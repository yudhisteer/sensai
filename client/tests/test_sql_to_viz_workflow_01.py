import os
import json
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
runner = AppRunner(config)  # Your existing dual-client AppRunner

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

class VisualizationModel(BaseModel):
    chart_type: str = Field(description="Type of chart (e.g., bar, line, pie).")
    x_axis: str = Field(description="Column for the x-axis.")
    y_axis: str = Field(description="Column for the y-axis.")
    title: str = Field(description="Title of the visualization.")

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

def triage_system_prompt(context_variables: dict) -> str:
    return """You are a triage assistant. Analyze the user query and determine its type:
    - If it’s a SQL-related question about data (e.g., averages, counts), call switch_to_sql_agent.
    - For other questions, do nothing (not implemented here).
    Do not answer the query yourself—route it to the appropriate agent."""

def sql_system_prompt(context_variables: dict) -> str:
    table_schema = context_variables.get("table_schema", None)
    table_name = context_variables.get("table_name", None)
    return f"""You are a SQL expert. You will be provided with user queries about the table '{table_name}'.
    The table has the following schema:
    {table_schema}

    Generate a SQL query that:
    1. Strictly follows this schema
    2. Uses the correct column names and data types
    3. Respects NULL/NOT NULL constraints
    4. Considers default values where applicable

    Return only the SQL query without any explanations.
    """

def sql_to_viz_system_prompt(context_variables: dict) -> str:
    sql_query = context_variables.get("sql_query", "unknown query")
    return f"""You are a transition agent. Given this SQL query:
    {sql_query}

    Call switch_to_viz_agent with the query to generate a visualization.
    """

def viz_system_prompt(context_variables: dict) -> str:
    sql_query = context_variables.get("sql_query", "unknown query")
    return f"""You are a visualization expert. Given this SQL query:
    {sql_query}

    Generate a visualization specification based on the query’s intent and the table schema:
    - Choose an appropriate chart type (e.g., bar, line, pie).
    - Specify x_axis and y_axis columns from the table.
    - Provide a descriptive title.
    """

# ------------------------------------------------------------------
# Switch Functions
# ------------------------------------------------------------------

def switch_to_sql_agent() -> FuncResult:
    """Route the query to the SQL agent."""
    return FuncResult(value="Routing to SQL agent", agent=sql_agent)

def switch_to_viz_agent(query: str) -> FuncResult:
    """Route the SQL query to the visualization agent."""
    updated_context = table_schema.copy()
    updated_context["sql_query"] = query
    return FuncResult(value=f"Generated SQL: {query}", agent=viz_agent, context_variables=updated_context)



# ------------------------------------------------------------------
# Pre-defined Agents
# ------------------------------------------------------------------

sql_agent = Agent(
    name="sql_agent",
    instructions=sql_system_prompt,
    response_model=SQLQueryModel,
    functions=[],
)

sql_to_viz_agent = Agent(
    name="sql_to_viz_agent",
    instructions=sql_to_viz_system_prompt,
    functions=[switch_to_viz_agent],
)

viz_agent = Agent(
    name="viz_agent",
    instructions=viz_system_prompt,
    response_model=VisualizationModel,
    functions=[],
)

triage_agent = Agent(
    name="triage_agent",
    instructions=triage_system_prompt,
    functions=[switch_to_sql_agent],
)



# ------------------------------------------------------------------
# Main Execution
# ------------------------------------------------------------------

if __name__ == "__main__":
    # SQL-related query with visualization
    query_sql = "What is the average temperature last month?"
    
    # Step 1: Run triage_agent to sql_agent
    response_sql = runner.run(
        agent=triage_agent,
        query=query_sql,
        context_variables=table_schema,
    )
    print("SQL Generation Response:")
    pretty_print_pydantic_model(response_sql)
    pretty_print_messages(response_sql.messages)
    print("-" * 100)

    # Extract the SQL query from the response
    sql_message = response_sql.messages[-1]["content"]
    sql_query = json.loads(sql_message)["query"]

    # Step 2: Run sql_to_viz_agent to viz_agent
    response_viz = runner.run(
        agent=sql_to_viz_agent,
        query=f"Visualize this query: {sql_query}",
        context_variables={"sql_query": sql_query, **table_schema},
    )
    print("Visualization Response:")
    pretty_print_pydantic_model(response_viz)
    pretty_print_messages(response_viz.messages)
    print("-" * 100)