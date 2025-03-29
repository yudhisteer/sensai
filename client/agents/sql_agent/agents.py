from client.agents.common.base import Agent
from client.agents.sql_agent.models import SQLResponse
from client.agents.sql_agent.prompts import sql_system_prompt

sql_agent = Agent(
    name="sql_agent",
    instructions=sql_system_prompt,
    response_format=SQLResponse,
)
