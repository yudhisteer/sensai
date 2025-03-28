from typing import Any, Callable, List, Optional, Type, Union

from openai import OpenAI
from pydantic import BaseModel

from .utils import function_to_json


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
    response_format: Optional[Type[BaseModel]] = None
    response_handler: Optional[Callable[[Any], Optional['Agent']]] = None

    def __init__(self, **data):
        super().__init__(**data)
        self._validate_configuration()

    def _validate_configuration(self):
        if self.response_format is not None and self.functions is not None:
            raise ValueError(
                f"Invalid configuration for agent '{self.name}': "
                "An Agent cannot have both `response_format` and `functions`. "
                "\n- For a parse agent, use `response_format` and `response_handler`, but do not include `functions`. "
                "\n- For a create agent, use `functions`, but do not include `response_format` and `response_handler`. "
            )

    def tools_in_json(self):
        if self.functions is None:
            return []
        return [function_to_json(f) for f in self.functions]

    def get_instructions(self, context_variables: dict = {}) -> str:
        if callable(self.instructions):
            return self.instructions(context_variables)
        return self.instructions


class AgentConfig:
    def __init__(self):
        self.max_interactions = 3
        self.model = None
        self.token_limit: int = 5000

    def with_max_interactions(self, max_interactions: int):
        self.max_interactions = max_interactions
        return self

    def with_model_client(self, model: OpenAI):
        self.model = model
        return self

    def with_token_limit(self, token_limit: int):
        self.token_limit = token_limit
        return self