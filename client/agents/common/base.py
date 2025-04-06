import json
from typing import Callable, List, Optional, Type, Union

from openai import OpenAI
from pydantic import BaseModel

from client.agents.common.utils import function_to_json


class Agent(BaseModel):
    """
    Data model for the agent
    """

    name: str = "Agent"
    model: str = "gpt-4o-mini"
    instructions: Union[str, Callable[[], str]] = "You are a helpful agent."
    functions: Optional[List[Callable]] = None
    parallel_tool_calls: bool = True
    tool_choice: str = None
    response_model: Optional[Type[BaseModel]] = None

    def tools_in_json(self):
        return [function_to_json(f) for f in self.functions]

    def get_instructions(self, context_variables: dict = {}) -> str:
        # if the instructions is a function, call it with the context variables
        if callable(self.instructions):
            return self.instructions(context_variables)
        # if the instructions is a string, return it
        return self.instructions
        # Note: when we parse in context_variables, our instructions will need to be a function that returns a string
        # Parsing the context_variables without any instructions as function, i.e, only string, will not appear
        # in the history of the messages


class AgentConfig:
    def __init__(self, config_dict: Optional[dict] = None):
        # Default values
        self.max_interactions = 3
        self.token_limit = 5000
        self.client = None

        # Parse config dictionary if provided
        if config_dict:
            self._parse_config(config_dict)

    def _parse_config(self, config_dict: dict):
        """Parse config dictionary for settings."""
        if "max_interactions" in config_dict:
            if not isinstance(config_dict["max_interactions"], int):
                raise ValueError("max_interactions must be an integer")
            self.max_interactions = config_dict["max_interactions"]
        if "token_limit" in config_dict:
            if not isinstance(config_dict["token_limit"], int):
                raise ValueError("token_limit must be an integer")
            self.token_limit = config_dict["token_limit"]
        if "api_key" in config_dict:
            self.api_key = config_dict["api_key"]

    @classmethod
    def from_json(cls, json_str: str):
        """Create an AgentConfig instance from a JSON string."""
        json_data = json.loads(json_str)
        return cls(json_data)

    @classmethod
    def from_file(cls, file_path: str):
        """Create an AgentConfig instance from a JSON file."""
        with open(file_path, "r") as f:
            json_data = json.load(f)
        return cls(json_data)

    def with_max_interactions(self, max_interactions: int):
        self.max_interactions = max_interactions
        return self

    def with_model_client(self, model: OpenAI):
        self.model = model
        return self

    def with_token_limit(self, token_limit: int):
        self.token_limit = token_limit
        return self
