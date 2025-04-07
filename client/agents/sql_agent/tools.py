import requests
import uuid
import tempfile
import os
import json
from shared.utils import debug_print



def execute_sql_query(sql_query: str, ENDPOINT_URL: str) -> str:
    """Call the API endpoint, store result in a temp file, and return a data_ref."""
    try:
        cleaned_sql_query = sql_query.rstrip(';').strip()
        payload = {"sql_query": cleaned_sql_query}

        # call API endpoint
        response = requests.post(ENDPOINT_URL, json=payload, timeout=3)
        response.raise_for_status() # `HTTPError`, if one occurred.
        
        result = response.json()["result"]
        
        # generate unique data_ref (filename)
        data_ref = f"temp_{uuid.uuid4().hex}.json"
        
        # create temp file and store data
        temp_dir = tempfile.gettempdir()
        data_ref_file_path = os.path.join(temp_dir, data_ref)
        
        with open(data_ref_file_path, 'w') as f:
            json.dump(result, f)
        
        debug_print(f"Data stored in temp file: {data_ref_file_path}")
        return data_ref_file_path
    
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
