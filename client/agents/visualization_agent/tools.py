from datetime import datetime
from typing import Dict, List, Optional, Union

import plotly.graph_objects as go
from pydantic import BaseModel, field_validator

from client.agents.visualization_agent.utils import process_data
from shared.logger_setup import get_logger
from shared.utils import debug_print
logger = get_logger(__name__)


def line_graph(
    data: List[Dict[str, str]],
    x_label: str = "Time",
    y_label: str = "y-axis",
    title: str = "Line Graph",
    secondary_y_label: Optional[str] = None,
) -> go.Figure:
    class PlotConfig(BaseModel):
        data: List[Union[str, Dict[str, Union[str, float, int]]]]
        x_label: str
        y_label: str
        title: str
        secondary_y_label: Optional[str] = None

        @field_validator("data")
        @classmethod
        def check_keys_exist(cls, v):
            # we just ensure data isn't empty
            if not v:
                raise ValueError("Data list is empty")
            return v

    config = PlotConfig(
        data=data,
        x_label=x_label,
        y_label=y_label,
        title=title,
        secondary_y_label=secondary_y_label,
    )

    # Process data to get x_key and y_keys
    try:
        x_key, y_keys = process_data(config.data)
    except ValueError as e:
        logger.error(f"Error processing data: {e}")
        # Create a simple figure with an error message
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {str(e)}",
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=20),
        )
        fig.update_layout(title="Error Processing Data")
        fig.write_html("output/plot.html")
        return fig

    # Extract and process x-axis data
    x_data = [entry[x_key] for entry in config.data]
    try:
        x_data = [
            datetime.strptime(val, "%Y-%m-%dT%H:%M:%SZ").strftime(
                "%Y-%m-%d %H:%M:%S+00"
            )
            for val in x_data
        ]
    except (ValueError, TypeError):
        try:
            # Try the other format
            x_data = [
                datetime.strptime(val, "%Y-%m-%d %H:%M:%S+00").strftime(
                    "%Y-%m-%d %H:%M:%S+00"
                )
                for val in x_data
            ]
        except (ValueError, TypeError):
            logger.warning("Could not parse dates, using as is")
            pass

    fig = go.Figure()
    colors = ["blue", "red", "green", "purple", "orange"]

    for i, y_key in enumerate(y_keys):
        try:
            y_data = [float(entry[y_key]) for entry in config.data]
        except (ValueError, TypeError) as e:
            logger.error(f"Error converting {y_key} data to float: {e}")
            continue

        fig.add_trace(
            go.Scatter(
                x=x_data,
                y=y_data,
                mode="lines+markers",
                name=y_key.capitalize(),
                line=dict(color=colors[i % len(colors)]),
                marker=dict(size=8),
                yaxis=(
                    "y2" if i == 1 else "y1"
                ),  # Second y_key uses secondary axis if present
            )
        )

    if not fig.data:
        # If no traces were added, add an error message
        fig.add_annotation(
            text="No valid data to plot",
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=20),
        )
        fig.update_layout(title="No Data to Plot")
        fig.write_html("output/plot.html")
        return fig

    layout = dict(
        title=config.title,
        xaxis_title=config.x_label,
        yaxis_title=config.y_label,
        legend_title="Variables",
        template="plotly_white",
        yaxis=dict(
            title=config.y_label,
            range=[
                min([float(entry[y_keys[0]]) for entry in config.data]) - 2,
                max([float(entry[y_keys[0]]) for entry in config.data]) + 2,
            ],  # Set range for y1
        ),
    )
    if len(y_keys) > 1 and config.secondary_y_label:
        layout["yaxis2"] = dict(
            title=config.secondary_y_label,
            overlaying="y",
            side="right",
            range=[
                min([float(entry[y_keys[1]]) for entry in config.data]) - 5,
                max([float(entry[y_keys[1]]) for entry in config.data]) + 5,
            ],  # Set range for y2
        )

    fig.update_layout(**layout)
    fig.write_html("output/plot.html")
    debug_print("Graph was successfully plotted")
    return fig


def plot_bar_graph(): ...


def plot_pie_chart(): ...


def plot_scatter_plot(): ...


if __name__ == "__main__":
    example_data = [{'id': 'dc978771-e511-451e-84b1-9a09304273a6', 'celsius': 23.5, 'fahrenheit': 74.3, 'created_at': '2025-04-02T10:00:00Z'}, {'id': '5473e5c9-1ce9-4820-ab20-5bc81fec7924', 'celsius': 15.75, 'fahrenheit': 60.35, 'created_at': '2025-04-02T12:00:00Z'}, {'id': '8a19ff54-ed54-4ae9-b4a4-de438a0bcf90', 'celsius': 30.2, 'fahrenheit': 86.36, 'created_at': '2025-04-02T14:00:00Z'}, {'id': 'd3708b65-07d0-4ee8-81ce-89b13ce1e2ed', 'celsius': -5.25, 'fahrenheit': 22.55, 'created_at': '2025-04-02T16:00:00Z'}, {'id': 'a877254e-a2fb-437f-b4c6-e718bb53e12c', 'celsius': 18.9, 'fahrenheit': 66.02, 'created_at': '2025-04-02T18:00:00Z'}]

    fig = line_graph(
        data=example_data, y_label="Variable1", secondary_y_label="Variable2"
    )
    # fig.show()
