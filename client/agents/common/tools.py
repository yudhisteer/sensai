from typing import Callable, Optional

from pydantic import BaseModel, Field


class ResponseBase(BaseModel):
    """
    Base class for all parsed response models. 
    It is used to generate a natural language response to the user.
    All parsed response models SHOULD inherit from this class.
    """
    response_to_user: Optional[str] = Field(
        default=None,
        description="Natural language response to the user"
    )


class ToolChoice(BaseModel):
    """
    Data model for the tool choice
    """

    tool_name: str = Field(description="The name of the tool to use.")
    reason_of_choice: str = Field(description="The reasoning for choosing the tool.")


class Tool:
    """
    Data model for the tool
    """

    def __init__(self, name: str, func: Callable, desc: str) -> None:
        self.desc = desc
        self.func = func
        self.name = name

