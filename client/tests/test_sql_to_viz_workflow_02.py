import os
import sqlparse
import json
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
    "max_interactions": 5,
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

def coordinator_system_prompt(context_variables: dict) -> str:
    return """You are a coordinator. Analyze the user query:
    - If it involves data analysis (e.g., averages, counts), call switch_to_planner.
    - Otherwise, call end_workflow to terminate.
    Do not answer the query yourself—route it appropriately."""

def planner_system_prompt(context_variables: dict) -> str:
    return """You are a planner. Given the user query, plan the steps:
    - For data analysis queries, the plan should be: 1) Generate SQL query, 2) Create visualization.
    - If the query cannot be planned (e.g., unsupported), call end_workflow.
    - Otherwise, call switch_to_supervisor to execute the plan.
    Respond with the plan as text (e.g., 'Plan: 1) Generate SQL query, 2) Create visualization')."""

def supervisor_system_prompt(context_variables: dict) -> str:
    plan = context_variables.get("plan", "No plan provided")
    step = context_variables.get("step", 1)
    return f"""You are a supervisor managing a workflow. The plan is:
    {plan}
    Current step: {step}

    Follow the plan:
    - Step 1: Call switch_to_sql_agent to generate a SQL query.
    - Step 2: Call switch_to_viz_agent to create a visualization.
    - If all steps are complete, call end_workflow.
    - If the plan fails, call end_workflow with an error message.
    """

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

def switch_to_planner() -> FuncResult:
    """Route the query to the planner agent."""
    return FuncResult(value="Routing to planner", agent=planner_agent)

def switch_to_supervisor(plan: str) -> FuncResult:
    """Route the query to the supervisor with the plan."""
    updated_context = table_schema.copy()
    updated_context["plan"] = plan
    updated_context["step"] = 1
    return FuncResult(value=f"Plan created: {plan}", agent=supervisor_agent, context_variables=updated_context)

def switch_to_sql_agent() -> FuncResult:
    """Route to the SQL agent to generate a query."""
    return FuncResult(value="Routing to SQL agent for query generation", agent=sql_agent)

def switch_to_viz_agent(query: str) -> FuncResult:
    """Route the SQL query to the visualization agent."""
    updated_context = table_schema.copy()
    updated_context["sql_query"] = query
    return FuncResult(value=f"Generated SQL: {query}", agent=viz_agent, context_variables=updated_context)

def end_workflow(error_message: str = "") -> FuncResult:
    """End the workflow, optionally with an error message."""
    return FuncResult(value=f"Workflow ended: {error_message}" if error_message else "Workflow completed successfully", agent=None)


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

supervisor_agent = Agent(
    name="supervisor_agent",
    instructions=supervisor_system_prompt,
    functions=[switch_to_sql_agent, switch_to_viz_agent, end_workflow],
)

planner_agent = Agent(
    name="planner_agent",
    instructions=planner_system_prompt,
    functions=[switch_to_supervisor, end_workflow],
)

coordinator_agent = Agent(
    name="coordinator_agent",
    instructions=coordinator_system_prompt,
    functions=[switch_to_planner, end_workflow],
)



# ------------------------------------------------------------------
# Main Execution
# ------------------------------------------------------------------

if __name__ == "__main__":
    # SQL-related query with visualization
    query_sql = "how much has the temperature maximum changed over the last 30 days?"
    
    # Step 1: Run coordinator to planner to supervisor to sql_agent
    response_sql = runner.run(
        agent=coordinator_agent,
        query=query_sql,
        context_variables=table_schema,
    )
    print("SQL Generation Response:")
    pretty_print_pydantic_model(response_sql)
    pretty_print_messages(response_sql.messages)
    print("-" * 100)

    # Extract the SQL query and context from the response
    sql_message = response_sql.messages[-1]["content"]
    sql_query = json.loads(sql_message)["query"]
    context = response_sql.context_variables
    context["sql_query"] = sql_query

    # Step 2: Run sql_to_viz_agent to viz_agent
    response_viz = runner.run(
        agent=sql_to_viz_agent,
        query=f"Visualize this query: {sql_query}",
        context_variables=context,
    )
    print("Visualization Response:")
    pretty_print_pydantic_model(response_viz)
    pretty_print_messages(response_viz.messages)
    print("-" * 100)