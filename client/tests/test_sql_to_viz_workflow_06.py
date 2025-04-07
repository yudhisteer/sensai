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
    - If the query involves data analysis (e.g., asking for averages, counts, sums, or any data retrieval from a table), the plan must be: "Plan: 1) Generate SQL query, 2) Execute SQL query, 3) Create visualization".
    - Examples of data analysis queries: "What is the average temperature last month?", "How many readings were taken?", "Show the temperature trend over time.", "What about the difference between mean and max temp today".
    - If the query is clearly unrelated to data analysis (e.g., "What is the weather like today?"), call end_workflow with an error message like "Query not supported for data analysis".
    - You MUST NOT generate the SQL query, visualization, or any other output beyond the plan.
    - After determining the plan, call switch_to_supervisor with the plan as the 'plan' argument to execute the plan. Do not respond with any text in your message content—pass the plan via the tool call.
    - Example: For "What is the average temperature last month?", call switch_to_supervisor(plan="Plan: 1) Generate SQL query, 2) Execute SQL query, 3) Create visualization").
    """


def supervisor_system_prompt(context_variables: dict) -> str:
    plan = context_variables.get("plan", "No plan provided")
    step = context_variables.get("step", 1)
    sql_query = context_variables.get("sql_query", "No SQL query generated yet")
    return f"""You are a supervisor managing a workflow. The plan is:
    {plan}
    Current step: {step}

    Follow the plan:
    - Step 1: Call switch_to_sql to generate a SQL query.
    - Step 2: Call execute_sql_query with the generated SQL query: '{sql_query}' to execute it.
    - Step 3: Call switch_to_viz to create a visualization.
    - Step 4: Call switch_to_plot to generate and display the plot.
    - If all steps are complete (Step 5), call end_workflow.
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

def switch_to_planner() -> FuncResult:
    """Route the query to the planner agent."""
    return FuncResult(value="Routing to planner", agent=planner_agent)


def switch_to_supervisor(plan: str) -> FuncResult:
    """Route the query to the supervisor with the current step."""
    context_variables["plan"] = plan
    context_variables["step"] = 1
    return FuncResult(
        value=f"Plan created: {plan}",
        agent=supervisor_agent,
        context_variables=context_variables,
    )


def feedback_to_supervisor_agent(context_variables: dict, history_msg: dict = None) -> FuncResult:
    """Route the query to the supervisor with the current step, storing sql_agent and viz_agent output if present."""
    if history_msg and "content" in history_msg:
        if history_msg.get("sender") == "sql_agent":
            # Store SQL query from SQL agent
            try:
                sql_query = json.loads(history_msg["content"])["query"]
                context_variables["sql_query"] = sql_query
            except json.JSONDecodeError:
                raise ("Error: Could not parse sql_agent response as JSON")
        elif history_msg.get("sender") == "viz_agent":
            # Store visualization spec from viz agent
            try:
                viz_spec = json.loads(history_msg["content"])
                context_variables["viz_spec"] = viz_spec
            except json.JSONDecodeError:
                raise ("Error: Could not parse viz_agent response as JSON")

    return AgentResult(
        value="Returning to supervisor",
        agent=supervisor_agent,
        context_variables=context_variables,
    )


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


def switch_to_sql() -> Agent:
    """Route the SQL query to the SQL agent."""
    context_variables["step"] = 2
    return sql_agent


def switch_to_viz(query: str) -> FuncResult:
    """Route the SQL query to the visualization agent."""
    context_variables["step"] = 4
    return FuncResult(
        value=f"Generated SQL: {query}",
        agent=viz_agent,
        context_variables=context_variables,
    )


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
        data_ref = context_variables.get("data_ref", None)
        
        if not viz_spec:
            raise ValueError("No visualization specification found")
        if not data_ref:
            raise ValueError("No data reference found")

        data = retrieve_data_from_temp_file(data_ref)
        if not data or not isinstance(data, list) or len(data) == 0:
            raise ValueError("No valid data retrieved for plotting")
        if len(data) != 1:
            raise ValueError("Expected single row for aggregate query")

        x_data = viz_spec["x_axis"]
        y_data = [data[0][viz_spec["y_axis"][0]]] 

        plt.bar(x_data, y_data)
        plt.title(viz_spec["title"])
        plt.xlabel("Measurement")
        plt.ylabel("Temperature (Fahrenheit)")
        plot_file_path = "output/generated_plot.png"
        context_variables["plot_file_path"] = plot_file_path
        context_variables["step"] = 5
        plt.savefig(plot_file_path)
        plt.close()

        return FuncResult(
            value="Plot generated and displayed successfully",
            agent=supervisor_agent,  # Return to supervisor after plotting
            context_variables=context_variables,
        )
    except Exception as e:
        return FuncResult(value=f"Error generating plot: {str(e)}", agent=None)



def switch_to_plot() -> FuncResult:
    """Route to the plot agent to generate and display the plot."""
    context_variables["step"] = 4  # Set Step 4 before switching
    return FuncResult(
        value="Switching to plot agent",
        agent=plot_agent,
        context_variables=context_variables,
    )


def end_workflow():
    """End the workflow"""
    return "Ending workflow"


# ------------------------------------------------------------------
# Pre-defined Agents
# ------------------------------------------------------------------

coordinator_agent = Agent(
    name="coordinator_agent",
    instructions=coordinator_system_prompt,
    functions=[switch_to_planner, end_workflow],
)


planner_agent = Agent(
    name="planner_agent",
    instructions=planner_system_prompt,
    functions=[switch_to_supervisor, end_workflow],
)

supervisor_agent = Agent(
    name="supervisor_agent",
    instructions=supervisor_system_prompt,
    functions=[switch_to_sql, execute_sql_query, switch_to_viz, switch_to_plot, end_workflow],
)

sql_agent = Agent(
    name="sql_agent",
    instructions=sql_system_prompt,
    response_model=SQLQueryModel,
    functions=[],
    next_agent=[feedback_to_supervisor_agent],
)


viz_agent = Agent(
    name="viz_agent",
    instructions=viz_system_prompt,
    response_model=VisualizationModel,
    functions=[],
    next_agent=[feedback_to_supervisor_agent],
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
        agent=coordinator_agent,
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

    def _execute_plot_graph():
        """Generate and display a plot based on the visualization spec and data from data_ref."""
        try:
            # Retrieve viz_spec and data_ref from context_variables
            viz_spec = context_variables.get("viz_spec", None)
            data_ref = context_variables.get("data_ref", None)
            
            if not viz_spec:
                raise ValueError("No visualization specification found in context_variables")
            if not data_ref:
                raise ValueError("No data reference found in context_variables")
            
            # Retrieve data from the temp file
            data = retrieve_data_from_temp_file(data_ref)
            print("DEBUG: Data:", data)
            if not data or not isinstance(data, list) or len(data) == 0:
                raise ValueError("No valid data retrieved for plotting")

            # Extract data for plotting (assuming data is a list of dicts from execute_sql_query)
            x_data = viz_spec["x_axis"]
            y_data = [data[0][viz_spec["y_axis"][0]]]

            # Create the plot based on chart_type
            if viz_spec["chart_type"] == "bar":
                plt.bar(x_data, y_data)
            elif viz_spec["chart_type"] == "line":
                plt.plot(x_data, y_data)
            elif viz_spec["chart_type"] == "pie":
                plt.pie(y_data, labels=x_data, autopct="%1.1f%%")
            else:
                raise ValueError(f"Unsupported chart type: {viz_spec['chart_type']}")

            # Set title and labels
            plt.title(viz_spec["title"])
            plt.xlabel(viz_spec["x_axis"][0])
            plt.ylabel(viz_spec["y_axis"][0])

            # Save the plot to a file
            plot_file_path = "output/generated_plot.png"
            plt.savefig(plot_file_path)

        except Exception as e:
            raise Exception(f"Error generating plot: {str(e)}")
        
    # _execute_plot_graph()

