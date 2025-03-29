from client.agents.common.base import Agent
from client.agents.visualization_agent.prompts import GRAPHING_SYSTEM_PROMPT
from client.agents.visualization_agent.tools import line_graph



def get_data_from_sql():
    return [
        {
            "id": "550e8400-e29b-41d4-a716-446655440013",
            "celsius": "20.50",
            "fahrenheit": "68.90",
            "created_at": "2025-03-22 12:00:00+00",
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440014",
            "celsius": "17.90",
            "fahrenheit": "64.20",
            "created_at": "2025-03-23 12:10:00+00",
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440015",
            "celsius": "29.30",
            "fahrenheit": "84.70",
            "created_at": "2025-03-24 12:20:00+00",
        },
    ]


# Line graph tool
def plot_line_graph():
    # retreive data
    data = get_data_from_sql()
    # pass data to line_graph tool
    fig = line_graph(data)
    return "Plot saved to plot.html"


# Bar graph tool
def plot_bar_graph():
    ...

# Pie chart tool
def plot_pie_chart():
    ...

# Scatter plot tool
def plot_scatter_plot():
    ...


# Visualization agent with its many graphing tools(line, bar, pie, etc.)
viz_agent = Agent(
    name="visualization_agent",
    instructions=GRAPHING_SYSTEM_PROMPT,
    functions=[plot_line_graph],
    parallel_tool_calls=False,
)