from openai import OpenAI

from .agents import SQL_Agent

from ..common.runner import AppRunner
from ..common.utils import pretty_print_messages

# Context variables
context_variables = {
    "table_name": "temperature_readings",
    "table_schema": """
        {
    "table_name": "temperature_readings",
    "schema": [
        {
        "column_name": "id",
        "data_type": "uuid",
        "is_nullable": "NO",
        "column_default": "uuid_generate_v4()"
        },
        {
        "column_name": "celsius",
        "data_type": "numeric",
        "is_nullable": "NO",
        "column_default": null
        },
        {
        "column_name": "fahrenheit",
        "data_type": "numeric",
        "is_nullable": "NO",
        "column_default": null
        },
        {
        "column_name": "created_at",
        "data_type": "timestamp with time zone",
        "is_nullable": "YES",
        "column_default": "now()"
        }
    ]
    }
    """,
}



if __name__ == "__main__":
    print("Starting the app")
    runner = AppRunner(client=OpenAI())
    messages = []
    # Choose entry agent
    agent = SQL_Agent
    while True:
        query = input("Enter your query: ")
        messages.append({"role": "user", "content": query})
        response = runner.run(agent, messages, context_variables)
        messages.extend(response.messages)
        agent = response.agent
        pretty_print_messages(response.messages)

    print("Finishing the app")
