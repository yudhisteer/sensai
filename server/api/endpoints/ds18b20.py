from fastapi import APIRouter, HTTPException, status

from server.db.supabase_client import SupabaseClientManager
from server.sensors.ds18b20.models import (
    SQLQueryRequest,
    SQLQueryResponse,
    TemperatureReading,
)
from server.sensors.ds18b20.tools import read_temp
from shared.logger_setup import get_logger

logger = get_logger(__name__)

# Initialize API Router
router = APIRouter()

# Initialize Supabase client
supabase = SupabaseClientManager().get_client()


@router.get(
    "/temperature/", response_model=TemperatureReading, status_code=status.HTTP_200_OK
)
async def read_temperature():
    """Endpoint to return the most recent stored temperature."""
    recent_reading = read_temp()
    if recent_reading:
        logger.info(f"Returning recent temperature: {recent_reading.model_dump()}")
        return recent_reading
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No temperature readings available",
        )


@router.post(
    "/temperature/sql", response_model=SQLQueryResponse, status_code=status.HTTP_200_OK
)
async def sql_query(request: SQLQueryRequest):
    """Execute a raw SQL query provided by the user."""
    try:
        sql_query = request.sql_query
        response = supabase.rpc("execute_sql", {"query": sql_query}).execute()
        if response.data and len(response.data) > 0:
            logger.info("SQL Query result successful!")
            return SQLQueryResponse(result=response.data[0])
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No data found"
        )
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query execution failed",
        )
