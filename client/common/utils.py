import json
import socket

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



def check_server_running(
    host: str = "127.0.0.1",
    port: int = 8000
) -> tuple[bool, str | None]:
    """
    Check if a server is running on the given host and port.
    Returns (is_running: bool, error_message: str | None).
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)  # 3-second timeout
            s.connect((host, port))
        return True, None
    except ConnectionRefusedError:
        return False, "The server is not running (connection refused)."
    except socket.TimeoutError:
        return False, "The server took too long to respond."
    except Exception as e:
        return False, f"Failed to check server: {str(e)}"

