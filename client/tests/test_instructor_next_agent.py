import os

from pydantic import BaseModel, Field

from client.agents.common.base import Agent, AgentConfig, AgentResult
from client.agents.common.runner import AppRunner
from client.agents.common.utils import pretty_print_messages


class Reply(BaseModel):
    content: str = Field(description="Your reply that we send to the customer.")
    category: str = Field(
        description="Category of the ticket: 'general', 'order', 'billing'"
    )
    urgent: bool = Field(description="Whether the ticket is urgent or not.")


def billing_agent_function(context_variables: dict):
    return AgentResult(value="This is the billing agent!", agent=billing_agent)


billing_agent = Agent(
    name="billing_agent",
    instructions="You're a helpful billing assistant that can help the customer with their billing questions.",
    functions=[],
)

trial_agent = Agent(
    name="trial_agent",
    instructions="You're a helpful customer care assistant that can classify incoming messages and create a response.",
    functions=[],
    response_model=Reply,
    next_agent=[billing_agent],
)

trial_agent_with_function = Agent(
    name="trial_agent_with_function",
    instructions="You're a helpful customer care assistant that can classify incoming messages and create a response.",
    functions=[],
    response_model=Reply,
    next_agent=[billing_agent_function],
)


if __name__ == "__main__":
    # configure the runner
    config_dict = {
        "max_interactions": 3,
        "token_limit": 1000,
        "api_key": os.getenv("OPENAI_API_KEY"),
    }
    config = AgentConfig(config_dict)
    runner = AppRunner(config)

    # 1. next_agent is an Agent
    response = runner.run(
        agent=trial_agent,
        query="Hi there, I have a question about my bill. Can you help me?",
        context_variables={},
    )
    # pretty_print_pydantic_model(response)
    pretty_print_messages(response.messages)
    print("-" * 100)

    # 2. next_agent is a function which returns an Agent
    response = runner.run(
        agent=trial_agent_with_function,
        query="Hi there, I have a question about my bill. Can you help me?",
        context_variables={},
    )
    pretty_print_messages(response.messages)
    print("-" * 100)
