import json
import os

from pydantic import BaseModel, Field

from client.agents.common.base import Agent, AgentConfig, FuncResult
from client.agents.common.runner import AppRunner
from client.agents.common.utils import pretty_print_messages

"""
This module demonstrates the core logic of agent switching and message routing using Pydantic models.

Core Workflow Logic:
1. Message Classification:
   - A primary agent receives the initial message
   - Uses a Pydantic model to structure the response with classification metadata
   - The model defines the schema for the agent's output

2. Agent Switching Mechanism:
   - The primary agent's next_agent parameter accepts either:
     a. A direct agent reference
     b. A function that returns an agent
   - The switching function receives context variables and history message
   - Based on the classification in the history message, routes to appropriate specialized agent

3. Message Flow:
   - Initial message → Primary Agent → Classification → Switch Logic → Specialized Agent
   - Each agent in the chain can access previous messages and context
   - The workflow maintains state through context variables and message history

This pattern enables dynamic routing of messages based on content classification while maintaining a clean separation of concerns between different agent specializations.
"""

class Reply(BaseModel):
    content: str = Field(description="Your reply that we send to the customer.")
    category: str = Field(
        description="Category of the ticket: 'general', 'order', 'billing'"
    )
    urgent: bool = Field(description="Whether the ticket is urgent or not.")


def billing_agent_function(context_variables: dict, history_msg: dict = None):
    return FuncResult(value="This is the billing agent!", agent=billing_agent)


billing_agent = Agent(
    name="billing_agent",
    instructions="You're a helpful billing assistant that can help the customer with their billing questions.",
    functions=[],
)

order_agent = Agent(
    name="order_agent",
    instructions="You're a helpful order assistant that can help the customer with their order questions.",
    functions=[],
)


general_agent = Agent(
    name="general_agent",
    instructions="You're a helpful general assistant that can help the customer with their general questions.",
    functions=[],
)


def switch_logic(context_variables: dict, history_msg: dict = None):
    # print("DEBUG: history_msg:", history_msg)
    if history_msg:
        # Extract category from the content JSON
        content = json.loads(history_msg["content"])
        category = content["category"]

        if category == "billing":
            return FuncResult(value="This is the billing agent!", agent=billing_agent)
        elif category == "order":
            return FuncResult(value="This is the order agent!", agent=order_agent)
        else:
            return FuncResult(value="This is the general agent!", agent=general_agent)
    return FuncResult(value="No history message available", agent=general_agent)


trial_agent = Agent(
    name="trial_agent",
    instructions="You're a helpful customer care assistant that can classify incoming messages and create a response.",
    functions=[],
    response_model=Reply,
    next_agent=[switch_logic],
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
        query="Hi there, I have a question about the weather. Can you help me?",
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
