import json
import os

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field

from client.agents.common.base import Agent, AgentConfig
from client.agents.common.runner import AppRunner
from client.agents.common.utils import pretty_print_messages
from client.common.utils import pretty_print_pydantic_model



class Reply(BaseModel):
    content: str = Field(description="Your reply that we send to the customer.")
    category: str = Field(description="Category of the ticket: 'general', 'order', 'billing'")
    urgent: bool = Field(description="Whether the ticket is urgent or not.")


trial_agent = Agent(
    name="trial_agent",
    instructions="You're a helpful customer care assistant that can classify incoming messages and create a response.",
    functions=[], # by default tools is None in runner when using response_model
    response_model=Reply,
)


if __name__ == "__main__":
    # configure the runner
    config_dict = {
        "max_interactions": 3,
        "token_limit": 1000,
        "api_key": os.getenv("OPENAI_API_KEY"),
    }
    config = AgentConfig(config_dict)

    # initialize the runner
    runner = AppRunner(config)

    # Run the trial agent
    response = runner.run(
        agent=trial_agent,
        query="Hi there, I have a question about my bill. Can you help me?",
    )
    pretty_print_pydantic_model(response)
    pretty_print_messages(response.messages)
    print("-" * 100)