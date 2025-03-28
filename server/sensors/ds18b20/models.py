from typing import Optional

from pydantic import BaseModel, Field


class TemperatureReading(BaseModel):
    celsius: float = Field(..., ge=-273.15)
    fahrenheit: float = Field(..., ge=0)
    id: Optional[str] = None
    created_at: Optional[str] = None


class SQLQueryResponse(BaseModel):
    result: dict = Field(..., description="Result of the executed SQL query")


class SQLQueryRequest(BaseModel):
    sql_query: str = Field(..., description="Raw SQL query to execute directly")
