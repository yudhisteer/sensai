from typing import Callable, Optional

from pydantic import BaseModel, Field


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

