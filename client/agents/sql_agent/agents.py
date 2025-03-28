from .tools import sql_system_prompt

from ..common.base import Agent
from .models import SQLResponse


SQL_Agent = Agent(
    name="SQL_Agent",
    instructions=sql_system_prompt,
    response_format=SQLResponse,
)
