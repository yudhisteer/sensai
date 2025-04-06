from typing import Any, Callable, List, Optional, Union

from pydantic import BaseModel

from client.agents.common.base import Agent


# AgentFunction defines the signature for functions that can be used by agents.
# These functions take no arguments and can return either:
# - A string (for direct responses)
# - An Agent instance (for switching to another agent)
# - A dictionary (for providing structured data or context)
AgentFunction = Callable[[], Union[str, "Agent", dict]]


class TaskResponse(BaseModel):
    """
    Encapsulates the possible response from a task.

    Attributes:
        messages (str): The response messages.
        agent (Agent): The agent instance, if applicable.
        context_variables (dict): A dictionary of context variables.
    """

    messages: List = []
    agent: Optional[Agent] = None
    context_variables: dict = {}


class FuncResult(BaseModel):
    """
    Encapsulates the possible return values for an agent function.

    Attributes:
        value (str): The result value as a string.
        agent (Agent): The agent instance, if applicable.
        context_variables (dict): A dictionary of context variables.
    """

    value: str = ""
    agent: Optional[Agent] = None
    context_variables: dict = {}