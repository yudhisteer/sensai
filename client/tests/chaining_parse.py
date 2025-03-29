from typing import Optional
from openai import OpenAI
from pydantic import Field

from ..agents.common.base import Agent
from ..agents.common.runner import AppRunner
from ..agents.common.tools import ResponseBase
from ..agents.common.utils import pretty_print_messages


#------------------------------------------
# Data models
#------------------------------------------

class EventExtraction(ResponseBase):
    """First LLM call: Extract basic event information"""

    description: str = Field(description="Raw description of the event")
    is_reservation_event: bool = Field(
        description="Whether this text describes a reservation event"
    )
    confidence_score: float = Field(description="Confidence score between 0 and 1")



class EventDetails(ResponseBase):
    """Second LLM call: Parse specific event details"""

    name: str = Field(description="Name of the person making the reservation")
    date: str = Field(
        description="Date and time of the reservation. Use ISO 8601 to format this value."
    )
    event_name: str = Field(description="Name of the event")
    participants: int = Field(description="Number of people in the reservation")
    reservation_request: Optional[str] = Field(
        description="Specific reservation request made by the user"
    )
    task_completed: bool = Field(description="Whether you got all information you needed")



class EventConfirmation(ResponseBase):
    """Third LLM call: Generate confirmation message"""

    confirmation_message: str = Field(
        description="Natural language confirmation message"
    )
    

#------------------------------------------
# Transfer functions
#------------------------------------------

def transfer_to_details(data_model: EventExtraction) -> Optional["Agent"]:
    """Transfer to details_agent if event is confirmed."""
    if data_model.is_reservation_event and data_model.confidence_score > 0.8:
        return extracting_event_details_agent
    else:
        return None


def transfer_to_confirmation(data_model: EventExtraction) -> Optional["Agent"]:
    """Transfer to confirmation_agent if event is confirmed."""
    if data_model.task_completed:
        return confirming_event_agent
    else:
        return None



#------------------------------------------
# Agents
#------------------------------------------

analyze_event_agent = Agent(
    name="analyze_event",
    instructions="Analyze if the text describes a reservation event.",
    response_format=EventExtraction,
    response_handler=transfer_to_details,
)


extracting_event_details_agent = Agent(
    name="extracting_event_details",
    instructions="Extract detailed event information. When dates reference 'next Tuesday' or similar relative dates, use this current date as reference.",
    response_format=EventDetails,
    response_handler=transfer_to_confirmation,
)


confirming_event_agent = Agent(
    name="confirming_event",
    instructions="Generate a natural confirmation message for the event. Sign of with your name; Jean-Philippe",
    response_format=EventConfirmation,
)



if __name__ == "__main__":
    print("Starting the Customer Support System")
    runner = AppRunner(client=OpenAI())
    messages = []
    context_variables = {}
    agent = analyze_event_agent
    while True:
        query = input("Enter your query: ")
        messages.append({"role": "user", "content": query})
        response = runner.run(agent, messages, context_variables)
        messages.extend(response.messages)
        pretty_print_messages(response.messages)
        # Update the active agent only if a new one is returned
        if response.agent:
            agent = response.agent
        # Optionally reset messages to avoid overloading history
        # messages = [messages[-1]]  # Keep only the latest user input
    print("Exiting the Customer Support System")