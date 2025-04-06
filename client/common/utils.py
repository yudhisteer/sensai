import json

from client.agents.common.types import TaskResponse


def pretty_print_pydantic_model(response: TaskResponse):
    """Generic function to print all fields of a Pydantic model from its JSON string."""
    COLORS = {
        "field": "\033[93m",  # Yellow
        "value": "\033[92m",  # Green
        "reset": "\033[0m",  # Reset
    }
    data = json.loads(response.messages[-1]["content"])
    try:
        for field_name, value in data.items():
            print(
                f"{COLORS['field']}{field_name}{COLORS['reset']}: {COLORS['value']}{value}{COLORS['reset']}"
            )
    except Exception as e:
        raise ValueError(f"Error parsing JSON: {e}")
