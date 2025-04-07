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

from client.agents.common.base import Agent, AgentConfig
from client.agents.common.runner import AppRunner
from client.agents.common.types import FuncResult
from client.agents.common.utils import pretty_print_messages
from client.common.utils import pretty_print_pydantic_model
from client.tests.schema import table_schema
from shared.utils import debug_print

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
    x_label: str = Field(description="Label for the x-axis.")
    y_label: str = Field(description="Label for the y-axis.")
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
    - Provide a descriptive title reflecting the query's intent.
    - Include a description explaining the chart choice.
    """


def execute_sql_query_prompt(context_variables: dict) -> str:
    sql_query = context_variables.get("sql_query", None)
    return f"""You are a SQL expert. You will be provided with a SQL query.
    {sql_query}
    Your task is to call the execute_sql_query tool to get the data.
    """

def plot_system_prompt(context_variables: dict) -> str:
    viz_spec = context_variables.get("viz_spec", "No visualization spec provided")
    data_ref = context_variables.get("data_ref", "No data reference provided")
    return f"""You are a plotting expert. Given the visualization spec:
    {viz_spec}
    and data stored at:
    {data_ref}

    Your task is to:
    Call execute_plot_graph_tool() with no arguments - it will use the data from context_variables
    """

# ------------------------------------------------------------------
#  Tools
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


def execute_sql_query(
    sql_query: str, endpoint_url: str = "http://127.0.0.1:8000/temperature/sql"
) -> FuncResult:
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


def execute_plot_graph_tool() -> str:
    """Generate and display a plot based on the visualization spec and data from context_variables."""
    try:
        viz_spec = context_variables.get("viz_spec", None)
        debug_print("Viz Spec:", viz_spec)
        data_ref = context_variables.get("data_ref", None)
        debug_print("Data Ref:", data_ref)

        if not viz_spec:
            raise ValueError("No visualization specification found")
        if not data_ref:
            raise ValueError("No data reference found")

        data = retrieve_data_from_temp_file(data_ref)
        debug_print("Data:", data)
        if not data or not isinstance(data, list) or len(data) == 0:
            raise ValueError("No valid data retrieved for plotting")
        if len(data) != 1:
            raise ValueError("Expected single row for aggregate query")

        x_data = viz_spec["x_axis"]
        debug_print("X Data:", x_data)

        y_data = [data[0][list(data[0].keys())[0]]]
        debug_print("Y Data:", y_data)

        plt.bar(x_data, y_data)
        plt.title(viz_spec["title"])
        plt.xlabel(viz_spec["x_label"])
        plt.ylabel(viz_spec["y_label"])
        plot_file_path = "output/generated_plot.png"
        context_variables["plot_file_path"] = plot_file_path
        context_variables["step"] = 5
        plt.savefig(plot_file_path)
        plt.show()
        plt.close()

        return "Graph generated successfully"
    except Exception as e:
        return f"Error generating plot: {str(e)}"


# ------------------------------------------------------------------
# Pre-defined Agents
# -----------------------------------------------------------------


sql_agent = Agent(
    name="sql_agent",
    instructions=sql_system_prompt,
    response_model=SQLQueryModel,
    functions=[],
    next_agent=[],
)



execute_sql_agent = Agent(
    name="execute_sql_agent",
    instructions=execute_sql_query_prompt,
    response_model=None,
    functions=[execute_sql_query],
    next_agent=[],
)


viz_agent = Agent(
    name="viz_agent",
    instructions=viz_system_prompt,
    response_model=VisualizationModel,
    functions=[],
    next_agent=[],
)

plot_agent = Agent(
    name="plot_agent",
    instructions=plot_system_prompt,
    functions=[execute_plot_graph_tool],
)


if __name__ == "__main__":
    # Step 1. Create a SQL query to get the data
    QUERY = "What is the average temperature Celcius from the data?"

    response = runner.run(
        agent=sql_agent,
        query=QUERY,
        context_variables=context_variables,
    )
    pretty_print_messages(response.messages)
    pretty_print_pydantic_model(response)
    sql_query = json.loads(response.messages[-1]["content"])["query"]
    print("SQL Query:", sql_query)
    print("*" * 100)

    # Step 2. Execute the SQL query
    response = runner.run(
        agent=execute_sql_agent,
        query=sql_query,
        context_variables=context_variables,
    )
    # Extract the file path from the tool response message
    tool_response = next(
        msg
        for msg in response.messages
        if msg["role"] == "tool" and msg["tool_name"] == "execute_sql_query"
    )
    data_ref = tool_response["content"].split(": ")[1]
    print("Data Ref:", data_ref)
    print("*" * 100)

    # Step 3. Generate a visualization specification
    response = runner.run(
        agent=viz_agent,
        query=f"Generate a visualization specification for the following SQL query: {sql_query}",
        context_variables=context_variables,
    )
    pretty_print_messages(response.messages)
    viz_spec = json.loads(response.messages[-1]["content"])
    print("Viz Spec:", viz_spec)
    print("*" * 100)

    # Step 4. Generate a plot
    # Add data reference to context variables
    context_variables["query"] = sql_query
    context_variables["data_ref"] = data_ref
    context_variables["viz_spec"] = viz_spec

    response = runner.run(
        agent=plot_agent,
        query="Plot the graph using the data from the data_ref and the viz_spec",
        context_variables=context_variables,
    )
    pretty_print_messages(response.messages)
    print("*" * 100)

    # _Step. Check the plot manually
    # print("Plotting...")
    # execute_plot_graph_tool()

    print("")
    print("Final Context Variables:")
    pprint(context_variables, indent=2, width=100)
