import os

from openai import OpenAI

from client.agents.common.base import Agent, AgentConfig
from client.agents.common.runner import AppRunner
from client.agents.common.utils import pretty_print_messages
from shared.utils import debug_print


def poem_instructions(context_variables: dict) -> str:
    return f"""Write a 2-3 lines poem about my cat using its name: {context_variables['cat_name']}. 
    Make sure to use its name at least 3 times."""


simple_poem_agent = Agent(
    name="Simple Poem Agent",
    instructions=poem_instructions,
    functions=[],
)



def simple_math(x: int, y: int) -> int:
    """Add two numbers together.

    Args:
        x: First number to add
        y: Second number to add

    Returns:
        The sum of x and y
    """
    return x + y


simple_math_agent = Agent(
    name="Simple Agent",
    instructions="""You are a simple agent that can answer math questions.
When you need to add two numbers, use the simple_math function with two integer parameters x and y.
For example, if asked to add 5 and 3, you would call simple_math(x=5, y=3).
Always specify both x and y parameters when using the function.""",
    functions=[simple_math],
)



if __name__ == "__main__":

    # configure the runner
    config_dict = {
        "max_interactions": 3,
        "token_limit": 1000,
        "client": OpenAI(api_key=os.getenv("OPENAI_API_KEY")),
    }
    config = AgentConfig(config_dict)

    # initialize the runner
    runner = AppRunner(config)

    # Run the math agent
    response = runner.run(
        agent=simple_math_agent,
        query="What is 5 + 3?",
    )
    pretty_print_messages(response.messages)
    print("-" * 100)

    # Run the poem agent
    response = runner.run(
        agent=simple_poem_agent,
        query="Write a poem about my cat using its name",
        context_variables={"cat_name": "butbut"},
    )
    pretty_print_messages(response.messages)
    print("-" * 100)


    response = runner.run(agent=simple_math_agent, 
                          query="What is 10 + 20?"
                          )
    pretty_print_messages(response.messages)
    print("-" * 100)
