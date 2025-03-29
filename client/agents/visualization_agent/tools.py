from datetime import datetime
from typing import Dict, List, Optional, Union
import json
import plotly.graph_objects as go
from pydantic import BaseModel, field_validator

from shared.logger_setup import get_logger
from shared.utils import debug_print

from client.agents.visualization_agent.utils import process_data

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
    x_key, y_keys = process_data(config.data)

    # Extract and process x-axis data
    x_data = [entry[x_key] for entry in config.data]
    try:
        x_data = [datetime.strptime(val, "%Y-%m-%d %H:%M:%S+00") for val in x_data]
    except (ValueError, TypeError):
        pass

    fig = go.Figure()
    colors = ["blue", "red", "green", "purple", "orange"]

    for i, y_key in enumerate(y_keys):
        try:
            y_data = [float(entry[y_key]) for entry in config.data]
        except ValueError as e:
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
    return fig


def plot_bar_graph(): ...


def plot_pie_chart(): ...


def plot_scatter_plot(): ...


if __name__ == "__main__":

    example_data = [
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

    fig = line_graph(
        data=example_data, y_label="Variable1", secondary_y_label="Variable2"
    )
    # fig.show()
