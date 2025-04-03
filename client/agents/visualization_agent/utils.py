from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel, field_validator



# ---------------------------------------------------
# Data Models
# ---------------------------------------------------
class DataEntry(BaseModel):
    id: str
    created_at: str

    # Allow additional fields (variable1, variable2, etc.) as strings
    class Config:
        extra = "allow"

    @field_validator("created_at")
    def validate_created_at(cls, v):
        try:
            # Ensure created_at matches the expected datetime format
            datetime.strptime(v, "%Y-%m-%d %H:%M:%S+00")
        except ValueError:
            try:
                # Try ISO format
                datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
                # Convert to the expected format
                dt = datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
                v = dt.strftime("%Y-%m-%d %H:%M:%S+00")
            except ValueError:
                raise ValueError(
                    "created_at must be in format 'YYYY-MM-DD HH:MM:SS+00' or 'YYYY-MM-DDTHH:MM:SSZ'"
                )
        return v

    @field_validator("*", mode="before")
    def ensure_strings(cls, v, info):
        # Ensure id and created_at are strings, but allow other fields to be numeric
        if info.field_name in ["id", "created_at"] and not isinstance(v, str):
            raise ValueError(f"Field {info.field_name} must be a string, got {type(v)}")
        return v


# ---------------------------------------------------
# Data Processing Functions
# ---------------------------------------------------


def process_data(data: List[Dict[str, str]]) -> tuple[str, List[str]]:
    """
    Process data function input and output example:

    Input:
    - data: List[Dict[str, str]]
      Example: [
          {"id": "1", "created_at": "2023-10-01 12:00:00+00", "variable1": "10", "variable2": "20"},
          {"id": "2", "created_at": "2023-10-01 12:05:00+00", "variable1": "15", "variable2": "25"}
      ]

    Output:
    - Returns a tuple:
      - x_key: str (e.g., "created_at")
      - y_keys: List[str] (e.g., ["variable1", "variable2"])
    """
    if not data:
        raise ValueError("Data list is empty")

    # Validate each entry using the Data model
    try:
        validated_data = [DataEntry(**entry) for entry in data]
    except ValueError as e:
        raise ValueError(f"Data validation failed: {str(e)}")

    first_entry = data[0]
    all_keys = list(first_entry.keys())
    non_y_keys = {"id", "created_at"}

    x_key = "created_at"
    if x_key not in all_keys:
        raise ValueError("Expected 'created_at' key in data, but not found")

    y_keys = [key for key in all_keys if key not in non_y_keys]
    if not y_keys:
        raise ValueError(
            "No y-axis variables found in data (expected 'variable1', 'variable2', etc.)"
        )

    return x_key, y_keys
