from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field


class TemperatureReading(BaseModel):
    id: UUID
    celsius: float
    fahrenheit: float
    created_at: datetime


class SQLQueryResponse(BaseModel):
    result: List[dict] = Field(description="Result of the executed SQL query as a list of JSON objects")

class SQLQueryRequest(BaseModel):
    sql_query: str = Field(description="Raw SQL query to execute directly")
