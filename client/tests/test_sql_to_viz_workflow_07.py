import json
import os
import tempfile
import uuid
from pprint import pprint
from typing import List

import matplotlib.pyplot as plt
import requests
import sqlparse
from pydantic import BaseModel, Field, field_validator

from client.agents.common.base import Agent, AgentConfig, AgentResult
from client.agents.common.runner import AppRunner
from client.agents.common.types import FuncResult
from client.agents.common.utils import pretty_print_messages
from client.tests.schema import table_schema

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
context_variables = table_schema

# ------------------------------------------------------------------
# Data Models
# ------------------------------------------------------------------


class SQLQueryModel(BaseModel):
    query: str

    @field_validator("query")
    def validate_sql_query(cls, value: str) -> str:
        value = value.rstrip(";").strip()  # remove trailing semicolon
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
    x_axis: List[str] = Field(description="Column for the x-axis.")
    y_axis: List[str] = Field(description="Columns for the y-axes.")
    title: str = Field(description="Title of the visualization.")
    description: str = Field(
        description="Explanation of why this chart type was chosen.", default=""
    )


# ------------------------------------------------------------------
# Instructions
# ------------------------------------------------------------------


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

    Generate a visualization specification based on the query's intent and the table schema:
    - Choose an appropriate chart type:
      - Use a **bar chart** for single aggregated values (e.g., MAX, AVG) to show the result clearly.
      - Use a **line chart** for time series data (e.g., trends over time with 'created_at').
      - Use a **pie chart** for proportions (2-5 categories).
      - Use a **scatter plot** for two numerical variables.
      - Use a **histogram** for distributions.
    - Specify x_axis and y_axis:
      - For single-value aggregates (e.g., MAX, AVG with no GROUP BY), set x_axis to a single label like ['Maximum'] and y_axis to the column name (e.g., ['max_temperature']).
      - For time series, x_axis should be 'created_at', y_axis the value.
      - For comparisons, x_axis is the grouping column, y_axis the value.
    - Provide a descriptive title reflecting the query’s intent.
    - Include a description explaining the chart choice.
    """

def plot_system_prompt(context_variables: dict) -> str:
    viz_spec = context_variables.get("viz_spec", "No visualization spec provided")
    data_ref = context_variables.get("data_ref", "No data reference provided")
    return f"""You are a plotting expert. Given the visualization spec:
    {viz_spec}
    and data stored at:
    {data_ref}

    Your task is to generate and display a plot. Call the execute_plot_graph tool to do this.
    """


# ------------------------------------------------------------------
# Switch Functions
# ------------------------------------------------------------------


def retrieve_data_from_temp_file(data_ref: str) -> dict:
    """Retrieve data from the temp file using the data_ref."""
    try:
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, data_ref)

        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                data = json.load(f)
            return data
        else:
            raise ValueError(f"Data file not found: {file_path}")
    except Exception as e:
        raise Exception(f"Error retrieving data: {e}")




def execute_sql_query(sql_query: str, endpoint_url: str = "http://127.0.0.1:8000/temperature/sql") -> FuncResult:
    """Call the API endpoint, store result in a temp file, and return a data_ref."""
    try:
        cleaned_sql_query = sql_query.rstrip(";").strip()
        payload = {"sql_query": cleaned_sql_query}
        response = requests.post(endpoint_url, json=payload, timeout=3)
        response.raise_for_status()

        result = response.json()["result"]
        data_ref = f"temp_{uuid.uuid4().hex}.json"
        temp_dir = tempfile.gettempdir()
        data_ref_file_path = os.path.join(temp_dir, data_ref)

        with open(data_ref_file_path, "w") as f:
            json.dump(result, f)
        context_variables["data_ref"] = data_ref_file_path
        context_variables["step"] = 3

        return FuncResult(
            value=f"Data stored at: {data_ref_file_path}",
            # agent=supervisor_agent,
            context_variables=context_variables,
        )

    except requests.exceptions.RequestException as e:
        return FuncResult(value=f"Error: API call failed: {e}", agent=None)
    except Exception as e:
        return FuncResult(value=f"Error storing data: {e}", agent=None)


def execute_plot_graph_tool():
    return "Ending workflow"


def switch_to_viz(context_variables: dict, history_msg: dict = None):
    """Switch to the viz agent."""
    sql_query = json.loads(history_msg["content"])["query"]
    context_variables["sql_query"] = sql_query
    return AgentResult(value="Switching to viz agent", agent=viz_agent, context_variables=context_variables)

def switch_to_plot(context_variables: dict, history_msg: dict = None):
    """Switch to the plot agent."""
    viz_spec = json.loads(history_msg["content"])
    context_variables["viz_spec"] = viz_spec
    return AgentResult(value="Switching to plot agent", agent=plot_agent, context_variables=context_variables)



# ------------------------------------------------------------------
# Pre-defined Agents
# -----------------------------------------------------------------


sql_agent = Agent(
    name="sql_agent",
    instructions=sql_system_prompt,
    response_model=SQLQueryModel,
    functions=[],
    next_agent=[switch_to_viz],
)


viz_agent = Agent(
    name="viz_agent",
    instructions=viz_system_prompt,
    response_model=VisualizationModel,
    functions=[],
    next_agent=[switch_to_plot],
)

plot_agent = Agent(
    name="plot_agent",
    instructions=plot_system_prompt,
    functions=[execute_plot_graph_tool],
)


if __name__ == "__main__":
    # SQL-related query with visualization
    QUERY = "What is the maximum temperature from the data?"

    response = runner.run(
        agent=sql_agent,
        query=QUERY,
        context_variables=context_variables,
    )

    print("Full Workflow Response:")
    pretty_print_messages(response.messages)
    print("-" * 100)

    print("DEBUG: Final Context variables:")
    context_variables.update(response.context_variables)
    pprint(context_variables, indent=2, width=100)
    print("-" * 100)
