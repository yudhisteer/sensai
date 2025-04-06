import os
import json
from typing import List
import sqlparse
from pydantic import BaseModel, Field, field_validator

from client.agents.common.base import Agent, AgentConfig
from client.agents.common.runner import AppRunner
from client.agents.common.types import FuncResult
from client.agents.common.utils import pretty_print_messages

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

config_dict = {
    "max_interactions": 10,
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
    y_axis: List[str] = Field(description="Columns for the y-axes.")
    title: str = Field(description="Title of the visualization.")
    description: str = Field(description="Explanation of why this chart type was chosen.", default="")

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
    table_schema = context_variables.get("table_schema", None)
    table_name = context_variables.get("table_name", None)
    return f"""You are a coordinator. Analyze the user query:
    - If it involves data analysis (e.g., averages, counts), call switch_to_planner.
    - Otherwise, call end_workflow to terminate.
    Do not answer the query yourself—route it appropriately.
    The table has the following schema:
    {table_schema} with table name {table_name}
    """


def planner_system_prompt(context_variables: dict) -> str:
    return """You are a planner. Given the user query, your ONLY task is to plan the steps:
    - If the query involves data analysis (e.g., asking for averages, counts, sums, or any data retrieval from a table), the plan must be: "Plan: 1) Generate SQL query, 2) Create visualization".
    - Examples of data analysis queries: "What is the average temperature last month?", "How many readings were taken?", "Show the temperature trend over time.", "What about the difference between mean and max temp today".
    - If the query is clearly unrelated to data analysis (e.g., "What is the weather like today?"), call end_workflow with an error message like "Query not supported for data analysis".
    - You MUST NOT generate the SQL query, visualization, or any other output beyond the plan.
    - After determining the plan, call switch_to_supervisor with the plan as the 'plan' argument to execute the plan. Do not respond with any text in your message content—pass the plan via the tool call.
    - Example: For "What is the average temperature last month?", call switch_to_supervisor(plan="Plan: 1) Generate SQL query, 2) Create visualization").
    """

def supervisor_system_prompt(context_variables: dict) -> str:
    plan = context_variables.get("plan", "No plan provided")
    step = context_variables.get("step", 1)
    return f"""You are a supervisor managing a workflow. The plan is:
    {plan}
    Current step: {step}

    Follow the plan:
    - Step 1: Call supervisor_to_sql_to_supervisor to generate a SQL query.
    - Step 2: Call switch_to_viz to create a visualization.
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


def viz_system_prompt(context_variables: dict) -> str:
    sql_query = context_variables.get("sql_query", "unknown query")
    return f"""You are a visualization expert. Given this SQL query:
    {sql_query}

    Generate a visualization specification based on the query’s intent and the table schema:
    - Choose an appropriate chart type (e.g., bar, line, pie) based on the following guidelines:
      - Use a **line chart** for time series data (e.g., trends over time, like 'created_at' on the x-axis with a numerical value on the y-axis).
      - Use a **bar chart** for comparisons between categories (e.g., comparing numerical values across different groups, like average temperature by month).
      - Use a **pie chart** for showing proportions or distributions (e.g., percentage of total across categories, but only if the query returns a small number of categories, typically 2-5).
      - Use a **scatter plot** for showing relationships between two numerical variables (e.g., celsius vs. fahrenheit).
      - Use a **histogram** for showing the distribution of a single numerical variable (e.g., distribution of temperature readings).
      - If the query returns a single value (e.g., an average), consider a **single-value visualization** (like a gauge or text display), but for this system, default to a bar chart with a single bar for simplicity.
    - Specify x_axis and y_axis columns from the table:
      - For time series (line chart), x_axis should be 'created_at'.
      - For comparisons (bar chart), x_axis should be the grouping column (e.g., a month or category), and y_axis should be the numerical value.
      - For scatter plots, x_axis and y_axis should be the two numerical columns being compared.
      - For pie charts, x_axis should be the category column, and y_axis should be the proportion or count.
    - Provide a descriptive title that reflects the query’s intent.
    - Include a description explaining why you chose this chart type, considering the query’s intent and data characteristics.
    """

def viz_to_supervisor_system_prompt(context_variables: dict) -> str:
    viz_spec = context_variables.get("viz_spec", "unknown visualization spec")
    return f"""You are a transition agent. Given this visualization specification:
    {viz_spec}

    Call switch_to_supervisor to return control to the supervisor for the next step.
    """


def sql_to_supervisor_system_prompt(context_variables: dict) -> str:
    sql_query = context_variables.get("sql_query", "unknown query")
    return f"""You are a transition agent. Given this SQL query:
    {sql_query}

    Call switch_to_supervisor to return control to the supervisor for the next step.
    """


# ------------------------------------------------------------------
# Switch Functions
# ------------------------------------------------------------------


def switch_to_planner() -> FuncResult:
    """Route the query to the planner agent."""
    return FuncResult(value="Routing to planner", agent=planner_agent)


def switch_to_supervisor(
    step: int = 1, 
    plan: str = "", 
    sql_query: str = "", 
    viz_spec: str = ""
) -> FuncResult:
    """Route the query to the supervisor with the current step."""
    updated_context = table_schema.copy()
    updated_context["plan"] = (
        plan if plan else "Plan: 1) Generate SQL query, 2) Create visualization"
    )
    updated_context["step"] = step
    if sql_query:
        updated_context["sql_query"] = sql_query
    if viz_spec:
        updated_context["viz_spec"] = viz_spec
    return FuncResult(
        value=f"Returning to supervisor at step {step}",
        agent=supervisor_agent,
        context_variables=updated_context,
    )


def supervisor_to_sql_to_supervisor() -> FuncResult:
    """Route to the SQL agent to generate a query, then chain to supervisor_agent."""
    # Step 1: Run sql_agent to generate the SQL query
    response = runner.run(
        agent=sql_agent,
        query=query_sql,
        context_variables=table_schema,
    )
    pretty_print_messages(response.messages)

    # Extract the SQL query from the response
    sql_message = response.messages[-1]["content"]
    sql_query = json.loads(sql_message)["query"]

    # Update context with the SQL query
    updated_context = table_schema.copy()
    updated_context["sql_query"] = sql_query

    # Return FuncResult pointing to supervisor_agent
    return FuncResult(
        value=f"SQL query generated: {sql_query}",
        agent=supervisor_agent,
        context_variables=updated_context,
    )


def switch_to_viz(query: str) -> FuncResult:
    """Route the SQL query to the visualization agent."""
    updated_context = table_schema.copy()
    updated_context["sql_query"] = query
    return FuncResult(
        value=f"Generated SQL: {query}",
        agent=viz_agent,
        context_variables=updated_context,
    )


def end_workflow(error_message: str = "") -> FuncResult:
    """End the workflow, optionally with an error message."""
    return FuncResult(
        value=f"Workflow ended: {error_message}"
        if error_message
        else "Workflow completed successfully",
        agent=None,
    )


# ------------------------------------------------------------------
# Pre-defined Agents
# ------------------------------------------------------------------

sql_agent = Agent(
    name="sql_agent",
    instructions=sql_system_prompt,
    response_model=SQLQueryModel,
    functions=[],
)


viz_agent = Agent(
    name="viz_agent",
    instructions=viz_system_prompt,
    response_model=VisualizationModel,
    functions=[],
)

viz_to_supervisor_agent = Agent(
    name="viz_to_supervisor_agent",
    instructions=viz_to_supervisor_system_prompt,
    functions=[switch_to_supervisor],
)

supervisor_agent = Agent(
    name="supervisor_agent",
    instructions=supervisor_system_prompt,
    functions=[supervisor_to_sql_to_supervisor, switch_to_viz, end_workflow],
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

    while True:
        # SQL-related query with visualization
        query_sql = input("Enter a query: ")

        response = runner.run(
            agent=coordinator_agent,
            query=query_sql,
            context_variables=table_schema,
        )
        print("Full Workflow Response:")
        # pretty_print_pydantic_model(response)
        pretty_print_messages(response.messages)
        print("-" * 100)
