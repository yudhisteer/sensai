from openai import OpenAI

from client.agents.visualization_agent.agents import viz_agent

from client.agents.common.runner import AppRunner
from client.agents.common.utils import pretty_print_messages


if __name__ == "__main__":
    print("Starting the app")
    runner = AppRunner(client=OpenAI())
    messages = []
    context_variables = {}
    agent = viz_agent
    while True:
        query = input("Enter your query: ")
        messages.append({"role": "user", "content": query})
        response = runner.run(agent, messages, context_variables)
        messages.extend(response.messages)
        agent = response.agent
        pretty_print_messages(response.messages)

    print("Finishing the app")
