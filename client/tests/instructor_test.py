import json
import os

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field

from client.agents.common.base import Agent, AgentConfig
from client.agents.common.runner import AppRunner
from client.agents.common.types import TaskResponse
from client.agents.common.utils import pretty_print_messages


def print_pydantic_model(response: TaskResponse):
    """Generic function to print all fields of a Pydantic model from its JSON string."""
    COLORS = {
        "field": "\033[93m",  # Yellow
        "value": "\033[92m",  # Green
        "reset": "\033[0m",  # Reset
    }
    data = json.loads(response.messages[-1]["content"])
    for field_name, value in data.items():
        print(
            f"{COLORS['field']}{field_name}{COLORS['reset']}: {COLORS['value']}{value}{COLORS['reset']}"
        )


class Reply(BaseModel):
    content: str = Field(description="Your reply that we send to the customer.")
    category: str = Field(
        description="Category of the ticket: 'general', 'order', 'billing'"
    )
    urgent: bool = Field(description="Whether the ticket is urgent or not.")


trial_agent = Agent(
    name="trial_agent",
    instructions="You're a helpful customer care assistant that can classify incoming messages and create a response.",
    functions=[],
    response_model=Reply,
)


if __name__ == "__main__":
    # configure the runner
    config_dict = {
        "max_interactions": 3,
        "token_limit": 1000,
        "client": instructor.from_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY"))),
    }
    config = AgentConfig(config_dict)

    # initialize the runner
    runner = AppRunner(config)

    # Run the math agent
    response = runner.run(
        agent=trial_agent,
        query="Hi there, I have a question about my bill. Can you help me?",
    )
    print_pydantic_model(response)
    pretty_print_messages(response.messages)
    print("-" * 100)
