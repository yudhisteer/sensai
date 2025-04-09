import socket

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

if __name__ == "__main__":
    is_running, error_message = check_server_running()
    print(f"Server is running: {is_running}")
    if error_message:
        print(f"Error: {error_message}")