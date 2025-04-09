import json
import os
import tempfile
import uuid
from typing import List

import matplotlib.pyplot as plt
import requests
import sqlparse
from pydantic import BaseModel, Field, field_validator

from client.agents.common.base import Agent, AgentConfig, FuncResult
from client.agents.common.runner import AppRunner
from client.agents.common.utils import pretty_print_messages
from client.common.utils import check_server_running
from client.tests.schema import table_schema
from shared.utils import debug_print

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

# Endpoint for the SQL API
API_ENDPOINT = "http://127.0.0.1:8000/temperature/sql"

# Check if the server is running
is_running, error_message = check_server_running()
if not is_running:
    raise ConnectionError(error_message)

# Configs for the agents
config_dict = {
    "max_interactions": 10,
    "token_limit": 1000,
    "api_key": os.getenv("OPENAI_API_KEY"),
}
config = AgentConfig(config_dict)
runner = AppRunner(config)

# Data for the workflow
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
    title: str = Field(
        description="Title of the visualization based on the schema and query."
    )
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


def supervisor_system_prompt(context_variables: dict) -> str:
    plan = context_variables.get("plan", "Generate a SQL query, execute it, create a visualization spec, and plot the result.")
    step = context_variables.get("step", 1)
    sql_query = context_variables.get("sql_query", "No SQL query generated yet")
    data_ref = context_variables.get("data_ref", "No data retrieved yet")
    viz_spec = context_variables.get("viz_spec", "No visualization spec generated yet")
    
    return f"""You are a supervisor managing a workflow. The plan is:
    {plan}
    Current step: {step}

    Follow this plan:
    - Step 1: Call route_to_sql_agent() to generate a SQL query.
    - Step 2: Call execute_sql_query with the generated SQL query: '{sql_query}' to execute it.
    - Step 3: Call route_to_viz_agent() to create a visualization specification.
    - Step 4: Call route_to_plot_agent() to generate and display the plot.
    - Step 5: If all steps are complete, call end_workflow() to finish the process.
    - If any step fails, call end_workflow() with an error message.
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


def execute_sql_query(sql_query: str, endpoint_url: str = API_ENDPOINT) -> FuncResult:
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
        context_variables["sql_query"] = cleaned_sql_query
        context_variables["step"] = 3  # Move to Step 3: Viz spec
        print("DEBUG: Context Variables in execute_sql_query:", context_variables)

        return FuncResult(
            value=f"Data stored at: {data_ref_file_path}",
            agent=supervisor_agent,
            context_variables=context_variables,
        )

    except requests.exceptions.RequestException as e:
        return FuncResult(value=f"Error: API call failed: {e}", agent=None)
    except Exception as e:
        return FuncResult(value=f"Error storing data: {e}", agent=None)


def execute_plot_graph_tool() -> FuncResult:
    """Generate and display a plot based on the visualization spec and data from context_variables."""
    try:
        viz_spec = context_variables.get("viz_spec", None)
        print("DEBUG: Viz Spec:", viz_spec)
        data_ref = context_variables.get("data_ref", None)
        print("DEBUG: Data Ref:", data_ref)

        if not viz_spec:
            raise ValueError("No visualization specification found")
        if not data_ref:
            raise ValueError("No data reference found")

        data = retrieve_data_from_temp_file(data_ref)
        print("DEBUG: Data:", data)
        if not data or not isinstance(data, list) or len(data) == 0:
            raise ValueError("No valid data retrieved for plotting")
        if len(data) != 1:
            raise ValueError("Expected single row for aggregate query")

        x_data = viz_spec["x_axis"]
        print("DEBUG: X Data:", x_data)

        y_data = [data[0][list(data[0].keys())[0]]] # TODO: Hardcoded for barchart
        print("DEBUG: Y Data:", y_data)

        plt.bar(x_data, y_data)
        plt.title(viz_spec["title"])
        plt.xlabel(viz_spec["x_label"])
        plt.ylabel(viz_spec["y_label"])
        plot_file_path = "output/generated_plot.png"
        context_variables["plot_file_path"] = plot_file_path
        context_variables["step"] = 5  # Move to Step 5: End
        plt.savefig(plot_file_path)
        plt.show()
        plt.close()

        return FuncResult(
            value="Graph generated successfully",
            agent=supervisor_agent,  # Terminate workflow
            context_variables=context_variables
        )
    except Exception as e:
        return FuncResult(value=f"Error generating plot: {str(e)}", agent=None)

# ------------------------------------------------------------------
# Routing
# -----------------------------------------------------------------



def feedback_to_plot_agent(context_variables: dict, history_msg: dict = None):
    if history_msg is None:
        print("DEBUG: No history message provided")
        return FuncResult(value="No history message provided", agent=None)
    # Store visualization spec from viz agent
    viz_spec = json.loads(history_msg["content"])
    print("DEBUG Plot Agent: Viz Spec:", viz_spec)
    context_variables["viz_spec"] = viz_spec
    context_variables["step"] = 4  # Move to Step 4: Plot
    print("DEBUG Context Variables:", context_variables)
    return FuncResult(
        value="Switching to plot_agent",
        agent=plot_agent,
        context_variables=context_variables
    )


def route_to_sql_agent():
    return sql_agent


def route_to_viz_agent():
    return viz_agent


def route_to_plot_agent():
    return plot_agent

def route_to_supervisor_agent():
    return supervisor_agent

def end_workflow() -> FuncResult:
    return FuncResult(value="Workflow completed successfully", agent=None, context_variables=context_variables)

# ------------------------------------------------------------------
# Agents
# -----------------------------------------------------------------

supervisor_agent = Agent(
    name="supervisor_agent",
    instructions=supervisor_system_prompt,
    functions=[route_to_sql_agent, route_to_viz_agent, route_to_plot_agent, end_workflow],
    next_agent=[],
    parallel_tool_calls=False,
)



plot_agent = Agent(
    name="plot_agent",
    instructions=plot_system_prompt,
    functions=[execute_plot_graph_tool],
    next_agent=[],
)

viz_agent = Agent(
    name="viz_agent",
    instructions=viz_system_prompt,
    response_model=VisualizationModel,
    functions=[],
    next_agent=[feedback_to_plot_agent],  # Move to plotting after spec generation
)

execute_sql_agent = Agent(
    name="execute_sql_agent",
    instructions=execute_sql_query_prompt,
    functions=[execute_sql_query],
    next_agent=[],
)


sql_agent = Agent(
    name="sql_agent",
    instructions=sql_system_prompt,
    response_model=SQLQueryModel,
    functions=[],
    next_agent=[execute_sql_agent],
)


triage_agent = Agent(
    name="triage_agent",
    instructions="You are a helpful triage agent. If the query involves data analysis (e.g., averages, counts), call route_to_supervisor_agent().",
    functions=[route_to_supervisor_agent],
    next_agent=[],
)



if __name__ == "__main__":

    while True:
        # SQL-related query with visualization
        QUERY = input("Enter a query: ")

        # Initialize context_variables with step and plan
        context_variables["step"] = 1
        context_variables["plan"] = f"Generate a SQL query based on the user query: {QUERY}, execute it, create a visualization spec, and plot the result."

        response = runner.run(
            agent=triage_agent,
            query=QUERY,
            context_variables=context_variables,
        )
        pretty_print_messages(response.messages)
        print("-" * 100)

    import pprint
    print("DEBUG: Final Context variables:")
    context_variables.update(response.context_variables)
    pprint.pprint(context_variables, indent=2, width=100)
    print("-" * 100)
