import requests
import uuid
import tempfile
import os
import json
from shared.utils import debug_print



def execute_sql_query(sql_query: str, ENDPOINT_URL: str) -> str:
    """Call the API endpoint, store result in a temp file, and return a data_ref."""
    try:
        payload = {"sql_query": sql_query}
        
        # call API endpoint
        response = requests.post(ENDPOINT_URL, json=payload, timeout=3)
        response.raise_for_status() # `HTTPError`, if one occurred.
        
        result = response.json()["result"]
        
        # generate unique data_ref (filename)
        data_ref = f"temp_{uuid.uuid4().hex}.json"
        
        # create temp file and store data
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, data_ref)
        
        with open(file_path, 'w') as f:
            json.dump(result, f)
        
        debug_print(f"Data stored in temp file: {file_path}")
        return data_ref
    
    except requests.exceptions.RequestException as e:
        raise Exception(f"API call failed: {e}")
    except Exception as e:
        raise Exception(f"Error storing data: {e}")


def retrieve_data_from_temp_file(data_ref: str) -> dict:
    """Retrieve data from the temp file using the data_ref."""
    try:
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, data_ref)
        
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
            debug_print(f"Data retrieved from temp file: {file_path}")
            return data
        else:
            raise ValueError(f"Data file not found: {file_path}")
    except Exception as e:
        raise Exception(f"Error retrieving data: {e}")
    

if __name__ == "__main__":
    data_ref = execute_sql_query("SELECT * FROM temperature_readings", "http://127.0.0.1:8000/temperature/sql")
    print(data_ref)
    data = retrieve_data_from_temp_file(data_ref)
    print(data)

