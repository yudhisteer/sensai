from client.agents.common.base import Agent
from pydantic import Field
from client.agents.visualization_agent.tools import line_graph
from client.agents.common.tools import ResponseBase
import requests
import uuid
import tempfile
import os
import json
from shared.utils import debug_print
from client.agents.common.runner import AppRunner
from openai import OpenAI
from client.agents.common.utils import pretty_print_messages

#---------------------------------------------------
# Data Models
#---------------------------------------------------

class SQLResponse(ResponseBase):
    is_sql_query: bool = Field(description="Whether the response is a SQL query")
    sql_query: str = Field(description="The SQL query to return as a string")




#---------------------------------------------------
# Tools
#---------------------------------------------------

data_ref = None

def execute_sql_query(sql_query: str, ENDPOINT_URL: str) -> str:
    """Call the API endpoint, store result in a temp file, and return a data_ref."""
    global data_ref
    try:
        payload = {"sql_query": sql_query}
        
        # Call the API endpoint
        response = requests.post(ENDPOINT_URL, json=payload, timeout=3)
        response.raise_for_status() # `HTTPError`, if one occurred.
        
        # Get the result from the response
        result = response.json()["result"]
        
        # Generate a unique data_ref (filename)
        data_ref = f"temp_{uuid.uuid4().hex}.json"
        
        # Create a temporary file and store the data
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, data_ref)
        
        with open(file_path, 'w') as f:
            json.dump(result, f)
        
        debug_print(f"Data stored in temp file: {file_path}")
        return file_path
    
    except requests.exceptions.RequestException as e:
        raise Exception(f"API call failed: {e}")
    except Exception as e:
        raise Exception(f"Error storing data: {e}")


def retrieve_data_from_temp_file(data_ref: str) -> dict:
    """Retrieve data from the temp file using the data_ref."""
    try:
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, data_ref)
        
        # Check if the file exists and read it
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
            debug_print(f"Data retrieved from temp file: {file_path}")
            return data
        else:
            raise ValueError(f"Data file not found: {file_path}")
    except Exception as e:
        raise Exception(f"Error retrieving data: {e}")
    


def plot_line_graph():
    global data_ref
    # use data_ref to retrieve data
    data = retrieve_data_from_temp_file(data_ref)
    debug_print(f"Data: {data}")
    fig = line_graph(data, y_label="Variable1", secondary_y_label="Variable2")
    return "Plot saved to plot.html"



#---------------------------------------------------
# Transfer Functions
#---------------------------------------------------

def transfer_to_visualization_agent(data_model: SQLResponse):
    if data_model.is_sql_query:
        data_ref = execute_sql_query(data_model.sql_query, "http://127.0.0.1:8000/temperature/sql")
        debug_print(f"Data reference: {data_ref}")
        return viz_agent
    else:
        return None
    

#---------------------------------------------------
# Prompts
#---------------------------------------------------

context_variables = {
    "table_schema": "CREATE TABLE temperature_readings (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), celsius FLOAT, fahrenheit FLOAT, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)",
    "table_name": "temperature_readings"
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
    

def viz_system_prompt(context_variables: dict) -> str:
    return """You are a visualization expert. The data is stored in a temp  which you do not need to worry about.
    Call the tool plot_line_graph which you have access to in order to plot a line graph.
    If the user asks to plot a line graph, call the `plot_line_graph_agent` tool which you have access to.
    """


#---------------------------------------------------
# Agents
#---------------------------------------------------

sql_agent = Agent(
    name="sql_agent",
    instructions=sql_system_prompt,
    response_format=SQLResponse,
    response_handler=transfer_to_visualization_agent,
)



viz_agent = Agent(
    name="visualization_agent",
    instructions=viz_system_prompt,
    functions=[plot_line_graph],
    parallel_tool_calls=False,
)




if __name__ == "__main__":
    print("Starting the app")
    runner = AppRunner(client=OpenAI())
    messages = []
    agent = sql_agent
    while True:
        query = input("Enter your query: ")
        messages.append({"role": "user", "content": query})
        response = runner.run(agent, messages, context_variables)
        messages.extend(response.messages)
        if response.agent:
            agent = response.agent
        pretty_print_messages(response.messages)

    print("Finishing the app")
